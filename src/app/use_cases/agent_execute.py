"""
Caso de uso: Ejecutar un agente.
Los agentes son globales — se identifican por agent_type.
Registra la ejecución como AgentTask con input, output, tokens y costo.
Valida cuota de la organización antes de ejecutar.
"""

from datetime import datetime, timezone

from domain.entities.agent import AgentTask
from domain.entities.base import StepStatus
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.agents.agent_registry import get_agent, list_available_agents
from app.agents.credit_costs import get_credit_cost
from infra.tools.openrouter_client import OpenRouterError


class AgentNotAvailableError(Exception):
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

    def __init__(self, task_repo: AgentTaskRepository) -> None:
        self._task_repo = task_repo

    async def execute(
        self,
        agent_type: str,
        user_input: str,
        organization_id: str,
        context: dict | None = None,
        organization=None,
        plan=None,
    ) -> AgentTask:
        # 1. Obtener instancia del agente (global)
        agent = get_agent(agent_type)
        if not agent:
            available = ", ".join(list_available_agents())
            raise AgentNotAvailableError(
                f"Agente '{agent_type}' no disponible. Agentes disponibles: {available}"
            )

        # 2. Validar cuota de la organización
        if organization and plan:
            credit_cost = get_credit_cost(agent_type)
            if organization.credits_used_this_month + credit_cost > plan.max_credits_per_month:
                remaining = plan.max_credits_per_month - organization.credits_used_this_month
                raise OrganizationQuotaExceededError(
                    f"Créditos insuficientes: necesitas {credit_cost} créditos, "
                    f"te quedan {remaining}/{plan.max_credits_per_month}. "
                    f"Actualiza tu plan para continuar."
                )

        # 3. Crear task en estado IN_PROGRESS
        started_at = datetime.now(timezone.utc)
        task = AgentTask(
            organization_id=organization_id,
            agent_type=agent_type,
            status=StepStatus.IN_PROGRESS,
            input_payload={"user_input": user_input, "context": context},
            started_at=started_at,
        )
        task = await self._task_repo.create(task)

        # 4. Ejecutar el agente (usa su default_model internamente)
        try:
            result = await agent.execute(
                user_input=user_input,
                context=context,
            )

            # 5. Calcular costo real
            finished_at = datetime.now(timezone.utc)
            tokens_input = result.get("tokens_prompt", 0)
            tokens_output = result.get("tokens_completion", 0)
            tokens_total = result.get("tokens_total", tokens_input + tokens_output)
            model_used = result.get("model", agent.default_model)
            cost = self._calculate_cost(tokens_input, tokens_output, model_used)

            task.status = StepStatus.COMPLETED
            task.output_payload = {
                "content": result["content"],
                "model": model_used,
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

            # Incrementar uso de créditos de la organización
            if organization:
                organization.credits_used_this_month += get_credit_cost(agent_type)

        except OpenRouterError as e:
            task.status = StepStatus.ERROR
            task.error_message = f"OpenRouter error {e.status_code}: {e.detail}"
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)

        except Exception as e:
            task.status = StepStatus.ERROR
            task.error_message = str(e)
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)

        await self._task_repo.update(task)
        return task

    def _calculate_cost(self, tokens_input: int, tokens_output: int, model: str) -> float:
        """
        Calcula el costo basado en los precios reales de OpenRouter.
        """
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

        cost_input = (tokens_input / 1_000_000) * pricing["input"]
        cost_output = (tokens_output / 1_000_000) * pricing["output"]

        total = cost_input + cost_output

        if tokens_input == 0 and tokens_output == 0:
            total_tokens = tokens_input + tokens_output
            avg_rate = (pricing["input"] + pricing["output"]) / 2
            total = (total_tokens / 1_000_000) * avg_rate

        return round(total, 6)
