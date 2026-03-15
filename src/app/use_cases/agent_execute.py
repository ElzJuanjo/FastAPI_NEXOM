"""
Caso de uso: Ejecutar un agente.
Registra la ejecución como AgentTask con input, output, tokens y costo.
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
    ) -> AgentTask:
        # 1. Obtener config del agente
        config = await self._config_repo.get_by_id(agent_config_id)
        if not config:
            raise AgentConfigNotFoundError(f"AgentConfig {agent_config_id} no encontrado")

        if not config.is_enabled:
            raise AgentDisabledError(f"El agente '{config.agent_type}' está deshabilitado")

        # 2. Obtener instancia del agente
        agent = get_agent(config.agent_type)
        if not agent:
            raise AgentNotAvailableError(f"Agente '{config.agent_type}' no disponible en el sistema")

        # 3. Crear task en estado IN_PROGRESS
        started_at = datetime.now(timezone.utc)
        task = AgentTask(
            agent_config_id=agent_config_id,
            status=StepStatus.IN_PROGRESS,
            input_payload={"user_input": user_input, "context": context},
            started_at=started_at,
        )
        task = await self._task_repo.create(task)

        # 4. Ejecutar el agente
        try:
            # Usar model_version del config, mapeado al formato OpenRouter
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

            # 5. Actualizar task con resultado exitoso
            finished_at = datetime.now(timezone.utc)
            task.status = StepStatus.COMPLETED
            task.output_payload = {
                "content": result["content"],
                "model": result["model"],
                "finish_reason": result["finish_reason"],
                "scraped_sources": result.get("scraped_sources"),
                "dropi_data": result.get("dropi_data"),
                "images": result.get("images"),
                "image_count": result.get("image_count"),
                "generation_params": result.get("generation_params"),
            }
            task.tokens_used = result["tokens_total"]
            task.cost_usd = self._estimate_cost(result["tokens_total"], model)
            task.finished_at = finished_at
            task.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            # Actualizar contadores del config
            config.tasks_completed += 1
            config.tasks_total += 1

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

        # Si ya viene con prefijo, retornarlo tal cual
        if "/" in model_version:
            return model_version

        return f"{prefix}/{model_version}"

    def _estimate_cost(self, total_tokens: int, model: str) -> float:
        """
        Estimación básica de costo.
        OpenRouter retorna el costo real en la respuesta, pero como fallback
        estimamos basándonos en tokens.
        """
        # Costos aproximados por 1K tokens (simplificado)
        cost_per_1k = {
            "openai/gpt-4o": 0.005,
            "openai/gpt-4o-mini": 0.00015,
            "anthropic/claude-sonnet-4-20250514": 0.003,
            "google/gemini-pro": 0.00025,
        }
        rate = cost_per_1k.get(model, 0.001)
        return round((total_tokens / 1000) * rate, 6)