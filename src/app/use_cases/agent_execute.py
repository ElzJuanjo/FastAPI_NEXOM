"""
Caso de uso: Ejecutar un agente.
Registra la ejecución como AgentTask con input, output, tokens y costo.
Valida cuota de la organización antes de ejecutar.
"""

from datetime import datetime, timezone

from domain.entities.agent import AgentTask
from domain.entities.base import StepStatus
from domain.repositories.agent_config_repository import AgentConfigRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.agents.agent_registry import get_agent
from infra.tools.openrouter_client import OpenRouterError


class AgentNotAvailableError(Exception):
    pass


class AgentConfigNotFoundError(Exception):
    pass


class AgentDisabledError(Exception):
    pass


class OrganizationQuotaExceededError(Exception):
    pass


# ---------------------------------------------------------------------------
# Precios reales de OpenRouter por modelo (USD por 1M tokens)
# ---------------------------------------------------------------------------

MODEL_PRICING = {
    # OpenAI
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00},
    "openai/gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Anthropic
    "anthropic/claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-4.6-sonnet-20260217": {"input": 3.00, "output": 15.00},
    # Google
    "google/gemini-3.1-flash-image-preview": {"input": 0.50, "output": 3.00},
    "google/gemini-3.1-flash-image-preview-20260226": {"input": 0.50, "output": 3.00},
    "google/gemini-2.5-flash-image-preview": {"input": 0.30, "output": 2.50},
}

# Fallback si el modelo no está en la tabla
DEFAULT_PRICING = {"input": 1.00, "output": 5.00}


class AgentExecute:

    def __init__(
        self,
        config_repo: AgentConfigRepository,
        task_repo: AgentTaskRepository,
    ) -> None:
        self._config_repo = config_repo
        self._task_repo = task_repo

    async def execute(
        self,
        agent_config_id: str,
        user_input: str,
        context: dict | None = None,
        organization=None,
        plan=None,
    ) -> AgentTask:
        # 1. Obtener config del agente
        config = await self._config_repo.get_by_id(agent_config_id)
        if not config:
            raise AgentConfigNotFoundError(f"AgentConfig {agent_config_id} no encontrado")

        if not config.is_enabled:
            raise AgentDisabledError(f"El agente '{config.agent_type}' está deshabilitado")

        # 2. Validar cuota de la organización
        if organization and plan:
            if organization.tasks_used_this_month >= plan.max_tasks_per_month:
                raise OrganizationQuotaExceededError(
                    f"Cuota mensual agotada: {organization.tasks_used_this_month}/{plan.max_tasks_per_month} tasks. "
                    f"Actualiza tu plan para continuar."
                )

        # 3. Obtener instancia del agente
        agent = get_agent(config.agent_type)
        if not agent:
            raise AgentNotAvailableError(f"Agente '{config.agent_type}' no disponible en el sistema")

        # 4. Crear task en estado IN_PROGRESS
        started_at = datetime.now(timezone.utc)
        task = AgentTask(
            agent_config_id=agent_config_id,
            status=StepStatus.IN_PROGRESS,
            input_payload={"user_input": user_input, "context": context},
            started_at=started_at,
        )
        task = await self._task_repo.create(task)

        # 5. Ejecutar el agente
        try:
            model = self._resolve_model(config.ai_provider, config.model_version)
            temperature = (config.config_params or {}).get("temperature", 0.7)
            max_tokens = (config.config_params or {}).get("max_tokens", 2048)

            result = await agent.execute(
                user_input=user_input,
                context=context,
                model_override=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 6. Calcular costo real
            finished_at = datetime.now(timezone.utc)
            tokens_input = result.get("tokens_prompt", 0)
            tokens_output = result.get("tokens_completion", 0)
            tokens_total = result.get("tokens_total", tokens_input + tokens_output)
            cost = self._calculate_cost(tokens_input, tokens_output, model)

            task.status = StepStatus.COMPLETED
            task.output_payload = {
                "content": result["content"],
                "model": result["model"],
                "finish_reason": result.get("finish_reason"),
                "scraped_sources": result.get("scraped_sources"),
                "dropi_data": result.get("dropi_data"),
                "images": result.get("images"),
                "image_count": result.get("image_count"),
                "generation_params": result.get("generation_params"),
            }
            task.tokens_used = tokens_total
            task.cost_usd = cost
            task.finished_at = finished_at
            task.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            # Actualizar contadores
            config.tasks_completed += 1
            config.tasks_total += 1

            # Incrementar uso de la organización
            if organization:
                organization.tasks_used_this_month += 1

        except OpenRouterError as e:
            task.status = StepStatus.ERROR
            task.error_message = f"OpenRouter error {e.status_code}: {e.detail}"
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)
            config.tasks_total += 1

        except Exception as e:
            task.status = StepStatus.ERROR
            task.error_message = str(e)
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)
            config.tasks_total += 1

        await self._task_repo.update(task)
        return task

    def _resolve_model(self, ai_provider: str, model_version: str) -> str:
        """Construye el identificador de modelo para OpenRouter."""
        provider_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "google",
        }
        prefix = provider_map.get(ai_provider, ai_provider)
        if "/" in model_version:
            return model_version
        return f"{prefix}/{model_version}"

    def _calculate_cost(self, tokens_input: int, tokens_output: int, model: str) -> float:
        """
        Calcula el costo basado en los precios reales de OpenRouter.
        Separa input y output tokens ya que tienen precios diferentes.
        """
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

        cost_input = (tokens_input / 1_000_000) * pricing["input"]
        cost_output = (tokens_output / 1_000_000) * pricing["output"]

        total = cost_input + cost_output

        # Si no tenemos el desglose, estimar con el total
        if tokens_input == 0 and tokens_output == 0:
            total_tokens = tokens_input + tokens_output
            avg_rate = (pricing["input"] + pricing["output"]) / 2
            total = (total_tokens / 1_000_000) * avg_rate

        return round(total, 6)