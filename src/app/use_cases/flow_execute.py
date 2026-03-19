"""
Caso de uso: Ejecutar un Flow completo.
Lee el Flow de la BD, ejecuta sus steps, y persiste los resultados.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.base import FlowStatus, StepStatus
from domain.repositories.flow_repository import FlowRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from domain.entities.agent import AgentTask
from app.orchestration.flow_state import FlowExecutionState
from app.orchestration.flow_executor import execute_flow
from app.agents.credit_costs import get_credit_cost, estimate_flow_credits


class FlowNotFoundError(Exception):
    pass


class FlowAlreadyRunningError(Exception):
    pass


class FlowQuotaExceededError(Exception):
    pass


class FlowExecute:

    def __init__(
        self,
        flow_repo: FlowRepository,
        task_repo: AgentTaskRepository,
    ) -> None:
        self._flow_repo = flow_repo
        self._task_repo = task_repo

    async def execute(self, flow_id: str, context: dict | None = None, organization=None, plan=None) -> dict:
        """
        Ejecuta un Flow: lee steps de la BD, corre agentes, persiste resultados.
        """
        # 1. Cargar Flow con steps
        flow = await self._flow_repo.get_by_id(flow_id)
        if not flow:
            raise FlowNotFoundError(f"Flow {flow_id} no encontrado")

        if flow.status == FlowStatus.RUNNING:
            raise FlowAlreadyRunningError(f"Flow {flow_id} ya está en ejecución")

        # 1.5 Validar cuota de créditos para todo el flow
        if organization and plan:
            agent_types = [step.agent_type for step in flow.steps]
            total_credits_needed = estimate_flow_credits(agent_types)
            remaining = plan.max_credits_per_month - organization.credits_used_this_month

            if remaining < total_credits_needed:
                raise FlowQuotaExceededError(
                    f"Créditos insuficientes para este flow: necesitas {total_credits_needed} créditos, "
                    f"te quedan {remaining}/{plan.max_credits_per_month}."
                )
                
        # 2. Marcar Flow como RUNNING
        flow.status = FlowStatus.RUNNING
        flow.started_at = datetime.now(timezone.utc)
        await self._flow_repo.update(flow)

        # 3. Preparar steps como dicts
        steps_data = [
            {
                "id": step.id,
                "agent_type": step.agent_type,
                "name": step.name,
                "order": step.order,
                "depends_on_step_id": step.depends_on_step_id,
            }
            for step in sorted(flow.steps, key=lambda s: s.order)
        ]

        # 4. Construir estado inicial
        initial_state: FlowExecutionState = {
            "flow_id": flow_id,
            "organization_id": flow.organization_id,
            "steps": steps_data,
            "step_outputs": {},
            "shared_context": context or {},
            "current_step_ids": [],
            "completed_step_ids": [],
            "failed_step_id": None,
            "error": None,
            "completed": False,
        }

        # 5. Ejecutar el Flow
        final_state = await execute_flow(initial_state)

        # 6. Persistir resultados en la BD
        total_tokens = 0
        total_duration = 0

        for step in flow.steps:
            output = final_state["step_outputs"].get(step.id)
            if not output:
                continue

            if output["status"] == "completed":
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
            elif output["status"] == "error":
                step.status = StepStatus.ERROR
            
            if not step.started_at:
                step.started_at = flow.started_at

            await self._flow_repo.update_step(step)

            # Crear AgentTask por cada step ejecutado
            task = AgentTask(
                organization_id=flow.organization_id,
                agent_type=step.agent_type,
                status=StepStatus.COMPLETED if output["status"] == "completed" else StepStatus.ERROR,
                flow_step_id=step.id,
                input_payload={"step_name": step.name, "agent_type": step.agent_type},
                output_payload={"content": output.get("content", "")[:5000]},
                error_message=output.get("error"),
                tokens_used=output.get("tokens_total", 0),
                started_at=flow.started_at,
                finished_at=datetime.now(timezone.utc),
                duration_ms=output.get("duration_ms", 0),
            )
            await self._task_repo.create(task)

            total_tokens += output.get("tokens_total", 0)
            total_duration += output.get("duration_ms", 0)

        # 7. Actualizar Flow final
        has_errors = final_state.get("error") is not None
        flow.status = FlowStatus.ERROR if has_errors else FlowStatus.COMPLETED
        flow.completed_at = datetime.now(timezone.utc)
        flow.progress_pct = 100.0
        await self._flow_repo.update(flow)
        
        # 7.5 Cobrar créditos por los steps completados exitosamente
        total_credits_consumed = 0
        if organization:
            for step in flow.steps:
                output = final_state["step_outputs"].get(step.id)
                if output and output["status"] == "completed":
                    credits = get_credit_cost(step.agent_type)
                    total_credits_consumed += credits

            organization.credits_used_this_month += total_credits_consumed

        # 8. Construir respuesta
        return {
            "flow_id": flow_id,
            "status": flow.status,
            "total_steps": len(steps_data),
            "completed_steps": len(final_state["completed_step_ids"]),
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "credits_consumed": total_credits_consumed,
            "credits_remaining": max(0, plan.max_credits_per_month - organization.credits_used_this_month) if plan else None,
            "step_results": {
                sid: {
                    "agent_type": out.get("agent_type"),
                    "status": out.get("status"),
                    "content_preview": (out.get("content") or "")[:500],
                    "tokens": out.get("tokens_total", 0),
                    "duration_ms": out.get("duration_ms", 0),
                    "error": out.get("error"),
                }
                for sid, out in final_state["step_outputs"].items()
            },
            "error": final_state.get("error"),
        }
