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
from app.use_cases.content_sanitizer import strip_internal_json
from domain.entities.conversation import Conversation, ConversationMessage


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

    async def execute(self, flow_id: str, context: dict | None = None, organization=None, plan=None, progress_emitter=None) -> dict:
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
                
        # 2. Reset steps from previous execution (if re-running)
        for step in flow.steps:
            step.status = StepStatus.PENDING
            step.started_at = None
            step.completed_at = None
            await self._flow_repo.update_step(step)

        # 3. Marcar Flow como RUNNING
        flow.status = FlowStatus.RUNNING
        flow.started_at = datetime.now(timezone.utc)
        flow.completed_at = None
        flow.progress_pct = 0.0
        await self._flow_repo.update(flow)

        # 4. Preparar steps como dicts
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

        # 5. Construir estado inicial
        initial_state: FlowExecutionState = {
            "flow_id": flow_id,
            "organization_id": flow.organization_id,
            "steps": steps_data,
            "step_outputs": {},
            "shared_context": {**(context or {}), "_org_id": flow.organization_id},
            "current_step_ids": [],
            "completed_step_ids": [],
            "failed_step_id": None,
            "error": None,
            "completed": False,
        }

        # 5. Ejecutar el Flow
        final_state = await execute_flow(initial_state, progress_emitter=progress_emitter)

        # 6. Persistir resultados en la BD
        total_tokens = 0
        total_duration = 0
        completed_count = 0

        for step in flow.steps:
            output = final_state["step_outputs"].get(step.id)
            if not output:
                continue

            if output["status"] == "completed":
                step.status = StepStatus.COMPLETED
                step.started_at = step.started_at or flow.started_at
                step.completed_at = datetime.now(timezone.utc)
                completed_count += 1
            elif output["status"] == "error":
                step.status = StepStatus.ERROR
                step.started_at = step.started_at or flow.started_at

            await self._flow_repo.update_step(step)

            # Crear AgentTask por cada step ejecutado
            task = AgentTask(
                organization_id=flow.organization_id,
                agent_type=step.agent_type,
                status=StepStatus.COMPLETED if output["status"] == "completed" else StepStatus.ERROR,
                flow_step_id=step.id,
                input_payload={"step_name": step.name, "agent_type": step.agent_type},
                output_payload={"content": (output.get("content") or "")[:5000]},
                error_message=output.get("error"),
                credits_used=get_credit_cost(step.agent_type) if output["status"] == "completed" else 0,
                started_at=flow.started_at,
                finished_at=datetime.now(timezone.utc),
                duration_ms=output.get("duration_ms", 0),
            )
            await self._task_repo.create(task)

            # Persist images as Creatives in BD (image_gen steps)
            if step.agent_type == "image_gen" and output["status"] == "completed":
                step_images = output.get("images", [])
                if step_images:
                    try:
                        from app.use_cases.creative_persist import persist_creative
                        session = self._flow_repo._session
                        gen_params = output.get("generation_params") if isinstance(output.get("generation_params"), dict) else {}

                        for img_url in step_images:
                            if isinstance(img_url, str) and img_url:
                                await persist_creative(
                                    session=session,
                                    base64_image=img_url,
                                    org_id=flow.organization_id,
                                    product_id=None,
                                    style=gen_params.get("style"),
                                    format=gen_params.get("aspect_ratio"),
                                    generation_prompt=gen_params.get("prompt"),
                                )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Error persisting flow creatives: {e}")

            # Auto-persist landing page sections (landing_page steps)
            if step.agent_type == "landing_page" and output["status"] == "completed":
                lp_content = output.get("content", "")
                if lp_content and len(lp_content) > 200:
                    try:
                        from app.use_cases.landing_auto_persist import auto_persist_landing_sections
                        session = self._flow_repo._session
                        await auto_persist_landing_sections(
                            session=session,
                            content=lp_content,
                            org_id=flow.organization_id,
                            brand_id=None,
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Error auto-persisting flow landing: {e}")
                        
            # Auto-persist brand identity (branding steps)
            if step.agent_type == "branding" and output["status"] == "completed":
                br_content = output.get("content", "")
                if br_content and len(br_content) > 300:
                    try:
                        from app.use_cases.brand_auto_persist import auto_persist_brand_identity
                        session = self._flow_repo._session
                        await auto_persist_brand_identity(
                            session=session,
                            content=br_content,
                            org_id=flow.organization_id,
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Error auto-persisting flow brand: {e}")
                        
            # Auto-persist copy assets (copywriting and ads steps)
            if step.agent_type in ("copywriting", "ads") and output["status"] == "completed":
                copy_content = output.get("content", "")
                if copy_content:
                    try:
                        from app.use_cases.copy_auto_persist import auto_persist_copy_assets
                        session = self._flow_repo._session
                        await auto_persist_copy_assets(
                            session=session,
                            content=copy_content,
                            org_id=flow.organization_id,
                            brand_id=None,
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"Error auto-persisting flow copy assets: {e}")

            total_tokens += output.get("tokens_total", 0)
            total_duration += output.get("duration_ms", 0)

        # 7. Actualizar Flow final
        has_errors = final_state.get("error") is not None
        total_steps = len(steps_data)
        flow.status = FlowStatus.ERROR if has_errors else FlowStatus.COMPLETED
        flow.completed_at = datetime.now(timezone.utc)
        flow.progress_pct = round((completed_count / total_steps) * 100, 1) if total_steps > 0 else 0
        await self._flow_repo.update(flow)

        # 7.5 Cobrar créditos
        total_credits_consumed = 0
        if organization:
            for step in flow.steps:
                output = final_state["step_outputs"].get(step.id)
                if output and output["status"] == "completed":
                    total_credits_consumed += get_credit_cost(step.agent_type)

            organization.credits_used_this_month += total_credits_consumed
            
        # 7.6 Create conversation from flow results
        conversation_id = None
        try:
            conversation = Conversation(
                organization_id=flow.organization_id,
                user_id=context.get("_user_id") if context else None,
                title=f"Flow: {flow.name}",
            )
            # We need the session to create the conversation
            session = self._flow_repo._session
            session.add(conversation)
            await session.flush()
            conversation_id = conversation.id

            # Add each step result as a message pair (user request + assistant response)
            for step in sorted(flow.steps, key=lambda s: s.order):
                output = final_state["step_outputs"].get(step.id)
                if not output:
                    continue

                agent_type = output.get("agent_type", step.agent_type)
                content = output.get("content", "")
                step_name = step.name

                if not content:
                    continue

                # User message: what was requested
                user_msg = ConversationMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=f"[Flow step {step.order}] {step_name}",
                )
                session.add(user_msg)

                # Assistant message: the result (clean for user display)
                assistant_msg = ConversationMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=strip_internal_json(content),
                    agent_type=agent_type,
                    meta_data={
                        "flow_id": flow_id,
                        "flow_step_id": step.id,
                        "step_order": step.order,
                        "duration_ms": output.get("duration_ms", 0),
                        "images": output.get("images"),
                    },
                )
                session.add(assistant_msg)

            # Update conversation metadata
            msg_count = len([s for s in flow.steps if final_state["step_outputs"].get(s.id)])
            conversation.message_count = msg_count * 2
            conversation.last_message_at = datetime.now(timezone.utc)
            conversation.agent_type = flow.steps[-1].agent_type if flow.steps else None

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error creating conversation from flow: {e}")
            conversation_id = None

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
            "conversation_id": conversation_id,
            "step_results": {
                sid: {
                    "agent_type": out.get("agent_type"),
                    "status": out.get("status"),
                    "content_preview": strip_internal_json((out.get("content") or ""))[:500],
                    "tokens": out.get("tokens_total", 0),
                    "duration_ms": out.get("duration_ms", 0),
                    "error": out.get("error"),
                }
                for sid, out in final_state["step_outputs"].items()
            },
            "error": final_state.get("error"),
        }