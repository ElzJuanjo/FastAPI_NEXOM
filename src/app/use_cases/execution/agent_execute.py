"""
Caso de uso: Ejecutar un agente.
Los agentes son globales — se identifican por agent_type.
Registra la ejecución como AgentTask con input, output, créditos y duración.
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
        # 1. Obtener instancia del agente
        agent = get_agent(agent_type)
        if not agent:
            available = ", ".join(list_available_agents())
            raise AgentNotAvailableError(
                f"Agent '{agent_type}' not available. Available agents: {available}"
            )

        # 2. Validar cuota de la organización
        credit_cost = get_credit_cost(agent_type)
        if organization and plan:
            if organization.credits_used_this_month + credit_cost > plan.max_credits_per_month:
                remaining = plan.max_credits_per_month - organization.credits_used_this_month
                raise OrganizationQuotaExceededError(
                    f"Insufficient credits: need {credit_cost}, "
                    f"remaining {remaining}/{plan.max_credits_per_month}. "
                    f"Upgrade your plan to continue."
                )

        # 3. Crear task en estado IN_PROGRESS
        started_at = datetime.now(timezone.utc)
        # ── Auto-rotate old agent tasks if near limit ──
        from app.use_cases.resource_limits import cleanup_if_needed
        await cleanup_if_needed(self._task_repo._session, organization_id, "agent_tasks")
        task = AgentTask(
            organization_id=organization_id,
            agent_type=agent_type,
            status=StepStatus.IN_PROGRESS,
            input_payload={"user_input": user_input, "context": context},
            started_at=started_at,
        )
        task = await self._task_repo.create(task)

        # 4. Ejecutar el agente
        try:
            result = await agent.execute(
                user_input=user_input,
                context=context,
            )

            finished_at = datetime.now(timezone.utc)
            model_used = result.get("model", agent.default_model)

            task.status = StepStatus.COMPLETED
            task.output_payload = {
                "content": result.get("content"),
                "model": model_used,
                "finish_reason": result.get("finish_reason"),
                "scraped_sources": result.get("scraped_sources"),
                "dropi_data": result.get("dropi_data"),
                "images": result.get("images"),
                "image_count": result.get("image_count"),
                "generation_params": result.get("generation_params"),
            }
            task.credits_used = credit_cost
            task.finished_at = finished_at
            task.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            # Incrementar uso de créditos
            if organization:
                organization.credits_used_this_month += credit_cost

        except OpenRouterError as e:
            task.status = StepStatus.ERROR
            task.error_message = f"OpenRouter error {e.status_code}: {e.detail}"
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)
            task.credits_used = 0

        except Exception as e:
            task.status = StepStatus.ERROR
            task.error_message = str(e)
            task.finished_at = datetime.now(timezone.utc)
            task.duration_ms = int((task.finished_at - started_at).total_seconds() * 1000)
            task.credits_used = 0

        await self._task_repo.update(task)
        return task