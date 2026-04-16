"""
Caso de uso: Reanudar un Flow pausado en selección de productos.

Cuando un Flow contiene un step de product_search y hay steps posteriores,
la ejecución se pausa tras el product_search esperando que el usuario elija
qué productos continúan. Este módulo:

1. Valida que el flow esté en estado PAUSED por selección de productos.
2. Persiste los productos elegidos en el catálogo (reutiliza el use case).
3. Reanuda la ejecución del flow inyectando `selected_products` en el
   shared_context para que los steps posteriores trabajen solo con ellos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.base import FlowStatus, StepStatus
from domain.repositories.flow_repository import FlowRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from domain.entities.agent import AgentTask
from domain.entities.conversation import Conversation, ConversationMessage
from app.orchestration.flow_state import FlowExecutionState
from app.orchestration.flow_executor import execute_flow
from app.agents.credit_costs import get_credit_cost, estimate_flow_credits
from app.use_cases.conversation.content_sanitizer import strip_internal_json
from app.use_cases.product.auto_persist import persist_selected_candidates


class FlowNotPausedError(Exception):
    pass


class FlowNoSelectionError(Exception):
    """Usuario intentó reanudar sin seleccionar al menos 1 producto."""
    pass


class FlowResumeWithSelection:

    def __init__(
        self,
        flow_repo: FlowRepository,
        task_repo: AgentTaskRepository,
    ) -> None:
        self._flow_repo = flow_repo
        self._task_repo = task_repo

    async def execute(
        self,
        flow_id: str,
        selected_products: list[dict],
        organization=None,
        plan=None,
        progress_emitter=None,
        user_id: str | None = None,
    ) -> dict:
        """
        Reanuda la ejecución del flow con los productos que el usuario eligió.

        Args:
            flow_id: ID del flow pausado
            selected_products: lista de productos elegidos por el usuario
                (mínimo 1, máximo 20). Se persisten en el catálogo y se
                inyectan en el contexto para los steps posteriores.
        """
        if not selected_products:
            raise FlowNoSelectionError(
                "Debe seleccionar al menos 1 producto para continuar el flow."
            )

        # Hard cap a 20 (defensivo; el DTO ya lo valida)
        selected_products = selected_products[:20]

        flow = await self._flow_repo.get_by_id(flow_id)
        if not flow:
            raise FlowNotPausedError(f"Flow {flow_id} no encontrado")

        if flow.status != FlowStatus.PAUSED:
            raise FlowNotPausedError(
                f"Flow {flow_id} no está pausado (status actual: {flow.status})"
            )

        pending = (flow.context or {}).get("_pending_selection") or {}
        if not pending:
            raise FlowNotPausedError(
                f"Flow {flow_id} está pausado pero no tiene estado de selección."
            )

        # 1. Persistir los productos elegidos en el catálogo
        session = self._flow_repo._session
        created_ids, skipped_names = await persist_selected_candidates(
            session=session,
            items=selected_products,
            org_id=flow.organization_id,
        )

        # 2. Validar créditos restantes para los steps pendientes
        remaining_step_ids = [
            s.id for s in flow.steps
            if s.id not in pending.get("completed_step_ids", [])
        ]
        remaining_agent_types = [
            s.agent_type for s in flow.steps
            if s.id in remaining_step_ids
        ]
        if organization and plan:
            credits_needed = estimate_flow_credits(remaining_agent_types)
            remaining = plan.max_credits_per_month - organization.credits_used_this_month
            if remaining < credits_needed:
                # No hay créditos para terminar — marcamos como error y salimos
                flow.status = FlowStatus.ERROR
                flow.completed_at = datetime.now(timezone.utc)
                await self._flow_repo.update(flow)
                return {
                    "flow_id": flow_id,
                    "status": "error",
                    "error": f"Créditos insuficientes para completar el flow "
                             f"(necesitas {credits_needed}, tienes {remaining}).",
                    "persisted_product_ids": created_ids,
                    "skipped_names": skipped_names,
                }

        # 3. Reconstruir el estado y reanudar la ejecución
        flow.status = FlowStatus.RUNNING
        flow.completed_at = None
        await self._flow_repo.update(flow)

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

        shared_context = {
            **(pending.get("shared_context") or {}),
            # INYECCIÓN CLAVE: los steps posteriores usan esta lista para
            # focalizar su output solo en los productos elegidos por el usuario.
            "selected_products": selected_products,
            "persisted_product_ids": created_ids,
            "_org_id": flow.organization_id,
        }

        resumed_state: FlowExecutionState = {
            "flow_id": flow_id,
            "organization_id": flow.organization_id,
            "steps": steps_data,
            "step_outputs": pending.get("step_outputs") or {},
            "shared_context": shared_context,
            "current_step_ids": [],
            "completed_step_ids": list(pending.get("completed_step_ids") or []),
            "failed_step_id": None,
            "error": None,
            "completed": False,
            "paused": False,
        }

        pause_step_id = pending.get("pause_step_id")
        final_state = await execute_flow(
            resumed_state,
            progress_emitter=progress_emitter,
            resume_from_step_id=pause_step_id,
        )

        # 4. Persistir resultados finales de los steps que corrieron en esta reanudación
        already_completed = set(pending.get("completed_step_ids") or [])
        total_tokens = 0
        total_duration = 0
        completed_count = len(already_completed)

        for step in flow.steps:
            output = final_state["step_outputs"].get(step.id)
            if not output:
                continue

            # Si ya estaba completado antes de la pausa, sus tokens/duration ya
            # se contaron en la corrida anterior; solo sumamos los nuevos.
            is_new = step.id not in already_completed

            if output["status"] == "completed":
                if is_new:
                    step.status = StepStatus.COMPLETED
                    step.started_at = step.started_at or flow.started_at
                    step.completed_at = datetime.now(timezone.utc)
                    completed_count += 1
            elif output["status"] == "error":
                step.status = StepStatus.ERROR
                step.started_at = step.started_at or flow.started_at

            if is_new:
                await self._flow_repo.update_step(step)

                # Sanitizar content para AgentTask (no exponer bloques internos en Activity)
                raw_content = output.get("content") or ""
                task = AgentTask(
                    organization_id=flow.organization_id,
                    agent_type=step.agent_type,
                    status=StepStatus.COMPLETED if output["status"] == "completed" else StepStatus.ERROR,
                    flow_step_id=step.id,
                    input_payload={"step_name": step.name, "agent_type": step.agent_type},
                    output_payload={"content": strip_internal_json(raw_content)},
                    error_message=output.get("error"),
                    credits_used=get_credit_cost(step.agent_type) if output["status"] == "completed" else 0,
                    started_at=flow.started_at,
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=output.get("duration_ms", 0),
                )
                await self._task_repo.create(task)

                # ── Auto-persist assets generados en los steps del resume ──
                # Misma lógica que flow/execute.py para que los assets se creen
                # sin importar si el flow corrió de un tirón o fue resumido.
                if output["status"] == "completed":
                    session = self._flow_repo._session

                    # Persist images as Creatives (image_gen steps)
                    if step.agent_type == "image_gen":
                        step_images = output.get("images", [])
                        if step_images:
                            try:
                                from app.use_cases.creative.persist import persist_creative
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
                                logging.getLogger(__name__).error(f"Error persisting resume flow creatives: {e}")

                    # Auto-persist landing page sections
                    if step.agent_type == "landing_page":
                        lp_content = raw_content
                        if lp_content and len(lp_content) > 200:
                            try:
                                from app.use_cases.landing.auto_persist import auto_persist_landing_sections
                                await auto_persist_landing_sections(
                                    session=session,
                                    content=lp_content,
                                    org_id=flow.organization_id,
                                    brand_id=None,
                                )
                            except Exception as e:
                                import logging
                                logging.getLogger(__name__).error(f"Error auto-persisting resume flow landing: {e}")

                    # Auto-persist brand identity
                    if step.agent_type == "branding":
                        br_content = raw_content
                        if br_content and len(br_content) > 300:
                            try:
                                from app.use_cases.brand.auto_persist import auto_persist_brand_identity
                                await auto_persist_brand_identity(
                                    session=session,
                                    content=br_content,
                                    org_id=flow.organization_id,
                                )
                            except Exception as e:
                                import logging
                                logging.getLogger(__name__).error(f"Error auto-persisting resume flow brand: {e}")

                    # Auto-persist copy assets (copywriting and ads)
                    if step.agent_type in ("copywriting", "ads"):
                        copy_content = raw_content
                        if copy_content:
                            try:
                                from app.use_cases.copy_asset.auto_persist import auto_persist_copy_assets
                                await auto_persist_copy_assets(
                                    session=session,
                                    content=copy_content,
                                    org_id=flow.organization_id,
                                    brand_id=None,
                                )
                            except Exception as e:
                                import logging
                                logging.getLogger(__name__).error(f"Error auto-persisting resume flow copy assets: {e}")

                total_tokens += output.get("tokens_total", 0)
                total_duration += output.get("duration_ms", 0)

        # 5. Finalizar flow
        has_errors = final_state.get("error") is not None
        total_steps = len(steps_data)
        flow.status = FlowStatus.ERROR if has_errors else FlowStatus.COMPLETED
        flow.completed_at = datetime.now(timezone.utc)
        flow.progress_pct = round((completed_count / total_steps) * 100, 1) if total_steps > 0 else 0
        # Limpiar el estado de pausa del context
        new_context = {k: v for k, v in (flow.context or {}).items() if k != "_pending_selection"}
        flow.context = new_context or None
        await self._flow_repo.update(flow)

        # 6. Cobrar créditos de los steps nuevos
        new_credits = 0
        if organization:
            for step in flow.steps:
                if step.id in already_completed:
                    continue
                output = final_state["step_outputs"].get(step.id)
                if output and output["status"] == "completed":
                    new_credits += get_credit_cost(step.agent_type)
            organization.credits_used_this_month += new_credits

        # 7. Crear conversation consolidada (igual que FlowExecute)
        conversation_id = None
        try:
            conversation = Conversation(
                organization_id=flow.organization_id,
                user_id=user_id,
                title=f"Flow: {flow.name}",
            )
            session.add(conversation)
            await session.flush()
            conversation_id = conversation.id

            for step in sorted(flow.steps, key=lambda s: s.order):
                output = final_state["step_outputs"].get(step.id)
                if not output:
                    continue

                agent_type = output.get("agent_type", step.agent_type)
                content = output.get("content", "")
                if not content:
                    continue

                user_msg = ConversationMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=f"[Flow step {step.order}] {step.name}",
                )
                session.add(user_msg)

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
                        "prompt_suggestions": output.get("prompt_suggestions"),
                        "generation_params": output.get("generation_params"),
                        "candidate_products": output.get("candidate_products"),
                    },
                )
                session.add(assistant_msg)

            msg_count = len([s for s in flow.steps if final_state["step_outputs"].get(s.id)])
            conversation.message_count = msg_count * 2
            conversation.last_message_at = datetime.now(timezone.utc)
            conversation.agent_type = flow.steps[-1].agent_type if flow.steps else None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error creating conversation from resumed flow: {e}")
            conversation_id = None

        return {
            "flow_id": flow_id,
            "status": flow.status,
            "paused": False,
            "total_steps": total_steps,
            "completed_steps": completed_count,
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "credits_consumed": new_credits,
            "credits_remaining": max(0, plan.max_credits_per_month - organization.credits_used_this_month) if plan else None,
            "conversation_id": conversation_id,
            "persisted_product_ids": created_ids,
            "skipped_names": skipped_names,
            "step_results": {
                sid: {
                    "agent_type": out.get("agent_type"),
                    "status": out.get("status"),
                    "content_preview": strip_internal_json((out.get("content") or ""))[:500],
                    "tokens": out.get("tokens_total", 0),
                    "duration_ms": out.get("duration_ms", 0),
                    "error": out.get("error"),
                    "candidate_products": out.get("candidate_products") or [],
                }
                for sid, out in final_state["step_outputs"].items()
            },
            "error": final_state.get("error"),
        }
