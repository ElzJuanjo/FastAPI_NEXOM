"""
Endpoints para ejecutar Flows — sync, streaming SSE, y resume con selección.
"""

import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.events.progress import ProgressEmitter, ProgressEvent
from app.dto.flow_execute_dto import (
    ExecuteFlowRequest, ExecuteFlowResponse, StepResultSummary,
    ResumeFlowWithSelectionRequest, ResumeFlowWithSelectionResponse,
)
from app.use_cases.flow.execute import (
    FlowExecute, FlowNotFoundError, FlowAlreadyRunningError, FlowQuotaExceededError,
)
from app.use_cases.flow.resume import (
    FlowResumeWithSelection, FlowNotPausedError, FlowNoSelectionError,
)
from interfaces.dependencies.flow_execute_dependencies import (
    get_flow_execute, get_flow_resume,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org
from domain.entities.organization import Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flows", tags=["Flow Execution"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_execute_response(result: dict) -> ExecuteFlowResponse:
    """Maps a FlowExecute result dict (including paused state) to the response DTO."""
    return ExecuteFlowResponse(
        flow_id=result["flow_id"],
        status=str(result["status"]),
        total_steps=result.get("total_steps", 0),
        completed_steps=result.get("completed_steps", 0),
        total_tokens=result.get("total_tokens", 0),
        total_duration_ms=result.get("total_duration_ms", 0),
        step_results={
            k: StepResultSummary(**v) for k, v in result.get("step_results", {}).items()
        },
        error=result.get("error"),
        paused=bool(result.get("paused")),
        pause_reason=result.get("pause_reason"),
        pause_step_id=result.get("pause_step_id"),
        candidate_products=result.get("candidate_products"),
        credits_consumed=result.get("credits_consumed", 0),
        credits_remaining=result.get("credits_remaining"),
        conversation_id=result.get("conversation_id"),
    )


# ── Sync endpoint ─────────────────────────────────────────────────────────────

@router.post("/execute", response_model=ExecuteFlowResponse)
async def execute_flow(
    body: ExecuteFlowRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowExecute = Depends(get_flow_execute),
    session: AsyncSession = Depends(get_session),
):
    plan = organization.plan

    flow_context = body.context or {}
    flow_context["_user_id"] = user_id
    if body.reference_image_url:
        flow_context["reference_image_url"] = body.reference_image_url
        flow_context["input_images"] = [body.reference_image_url]

    try:
        result = await use_case.execute(
            flow_id=body.flow_id,
            context=flow_context,
            organization=organization,
            plan=plan,
        )
    except FlowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FlowAlreadyRunningError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FlowQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Flow execution error: {str(e)}")

    await session.commit()
    return _build_execute_response(result)


# ── SSE streaming endpoint ───────────────────────────────────────────────────

@router.post("/execute/stream")
async def execute_flow_stream(
    body: ExecuteFlowRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowExecute = Depends(get_flow_execute),
    session: AsyncSession = Depends(get_session),
):
    """Execute a flow with real-time SSE progress per step."""
    plan = organization.plan
    emitter = ProgressEmitter()

    flow_context = body.context or {}
    flow_context["_user_id"] = user_id
    if body.reference_image_url:
        flow_context["reference_image_url"] = body.reference_image_url
        flow_context["input_images"] = [body.reference_image_url]

    async def stream_generator():
        try:
            yield emitter.to_sse(ProgressEvent(
                stage="starting", pct=2,
                message="Preparing flow execution...",
            ))

            result_holder = {}
            error_holder = {}

            async def run_flow():
                try:
                    r = await use_case.execute(
                        flow_id=body.flow_id,
                        context=flow_context,
                        organization=organization,
                        plan=plan,
                        progress_emitter=emitter,
                    )
                    result_holder["data"] = r
                except FlowNotFoundError as e:
                    error_holder["error"] = f"Flow not found: {e}"
                except FlowAlreadyRunningError as e:
                    error_holder["error"] = f"Flow already running: {e}"
                except FlowQuotaExceededError as e:
                    error_holder["error"] = f"Insufficient credits: {e}"
                except Exception as e:
                    error_holder["error"] = str(e)
                finally:
                    await emitter.done()

            flow_task = asyncio.create_task(run_flow())

            async for event in emitter:
                yield emitter.to_sse(event)

            await flow_task

            if error_holder:
                yield emitter.to_sse_error(error_holder["error"])
                return

            result = result_holder.get("data", {})
            await session.commit()

            step_results = {}
            for sid, out in result.get("step_results", {}).items():
                step_results[sid] = {
                    "agent_type": out.get("agent_type"),
                    "status": out.get("status"),
                    "content_preview": out.get("content_preview", ""),
                    "tokens": out.get("tokens", 0),
                    "duration_ms": out.get("duration_ms", 0),
                    "error": out.get("error"),
                    "candidate_products": out.get("candidate_products") or [],
                }

            done_payload = {
                "flow_id": result["flow_id"],
                "status": str(result["status"]),
                "total_steps": result.get("total_steps", 0),
                "completed_steps": result.get("completed_steps", 0),
                "total_tokens": result.get("total_tokens", 0),
                "total_duration_ms": result.get("total_duration_ms", 0),
                "credits_consumed": result.get("credits_consumed", 0),
                "credits_remaining": result.get("credits_remaining"),
                "conversation_id": result.get("conversation_id"),
                "step_results": step_results,
                "error": result.get("error"),
                # ── Campos de pausa ──
                "paused": bool(result.get("paused")),
                "pause_reason": result.get("pause_reason"),
                "pause_step_id": result.get("pause_step_id"),
                "candidate_products": result.get("candidate_products"),
            }

            yield emitter.to_sse_done(done_payload)

        except Exception as e:
            logger.error(f"Flow SSE stream error: {e}")
            yield emitter.to_sse_error(str(e))

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Resume with product selection (streaming) ───────────────────────────────

@router.post("/{flow_id}/resume-with-selection/stream")
async def resume_flow_with_selection_stream(
    flow_id: str,
    body: ResumeFlowWithSelectionRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowResumeWithSelection = Depends(get_flow_resume),
    session: AsyncSession = Depends(get_session),
):
    """Reanuda un flow pausado con SSE para mantener viva la barra de progreso.

    Mismo contrato que /resume-with-selection pero con streaming de eventos
    para que el frontend pueda continuar la barra desde el porcentaje
    donde se pausó (no vuelve a 0).
    """
    plan = organization.plan
    selected_dicts = [item.model_dump() for item in body.selected_products]
    emitter = ProgressEmitter()

    async def stream_generator():
        try:
            yield emitter.to_sse(ProgressEvent(
                stage="resuming", pct=50,
                message="Resuming flow with your selection...",
            ))

            result_holder = {}
            error_holder = {}

            async def run_resume():
                try:
                    r = await use_case.execute(
                        flow_id=flow_id,
                        selected_products=selected_dicts,
                        organization=organization,
                        plan=plan,
                        progress_emitter=emitter,
                        user_id=user_id,
                    )
                    result_holder["data"] = r
                except FlowNoSelectionError as e:
                    error_holder["error"] = f"Selection required: {e}"
                except FlowNotPausedError as e:
                    error_holder["error"] = f"Flow not paused: {e}"
                except Exception as e:
                    logger.error(f"Resume stream error: {e}")
                    error_holder["error"] = str(e)
                finally:
                    await emitter.done()

            resume_task = asyncio.create_task(run_resume())

            async for event in emitter:
                yield emitter.to_sse(event)

            await resume_task

            if error_holder:
                yield emitter.to_sse_error(error_holder["error"])
                return

            result = result_holder.get("data", {})
            await session.commit()

            step_results = {}
            for sid, out in result.get("step_results", {}).items():
                step_results[sid] = {
                    "agent_type": out.get("agent_type"),
                    "status": out.get("status"),
                    "content_preview": out.get("content_preview", ""),
                    "tokens": out.get("tokens", 0),
                    "duration_ms": out.get("duration_ms", 0),
                    "error": out.get("error"),
                    "candidate_products": out.get("candidate_products") or [],
                }

            done_payload = {
                "flow_id": result["flow_id"],
                "status": str(result["status"]),
                "paused": bool(result.get("paused")),
                "total_steps": result.get("total_steps", 0),
                "completed_steps": result.get("completed_steps", 0),
                "total_tokens": result.get("total_tokens", 0),
                "total_duration_ms": result.get("total_duration_ms", 0),
                "credits_consumed": result.get("credits_consumed", 0),
                "credits_remaining": result.get("credits_remaining"),
                "conversation_id": result.get("conversation_id"),
                "persisted_product_ids": result.get("persisted_product_ids") or [],
                "skipped_names": result.get("skipped_names") or [],
                "step_results": step_results,
                "error": result.get("error"),
            }

            yield emitter.to_sse_done(done_payload)

        except Exception as e:
            logger.error(f"Resume SSE stream error: {e}")
            yield emitter.to_sse_error(str(e))

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Resume with product selection ────────────────────────────────────────────

@router.post("/{flow_id}/resume-with-selection", response_model=ResumeFlowWithSelectionResponse)
async def resume_flow_with_selection(
    flow_id: str,
    body: ResumeFlowWithSelectionRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowResumeWithSelection = Depends(get_flow_resume),
    session: AsyncSession = Depends(get_session),
):
    """
    Reanuda un flow pausado tras product_search con los productos que el usuario eligió.

    - Requiere que el flow esté en status=paused con _pending_selection en context.
    - Persiste los productos elegidos (score real + bucket correspondiente).
    - Los inyecta como `selected_products` en el shared_context para que los steps
      posteriores (image_gen, ads, copywriting, etc.) solo trabajen con ellos.
    - Mínimo 1 producto, máximo 20 (validado por DTO).
    """
    plan = organization.plan
    selected_dicts = [item.model_dump() for item in body.selected_products]

    try:
        result = await use_case.execute(
            flow_id=flow_id,
            selected_products=selected_dicts,
            organization=organization,
            plan=plan,
            user_id=user_id,
        )
    except FlowNoSelectionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FlowNotPausedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Resume flow error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flow resume error: {str(e)}",
        )

    await session.commit()

    return ResumeFlowWithSelectionResponse(
        flow_id=result["flow_id"],
        status=str(result["status"]),
        paused=bool(result.get("paused")),
        total_steps=result.get("total_steps", 0),
        completed_steps=result.get("completed_steps", 0),
        total_tokens=result.get("total_tokens", 0),
        total_duration_ms=result.get("total_duration_ms", 0),
        credits_consumed=result.get("credits_consumed", 0),
        credits_remaining=result.get("credits_remaining"),
        conversation_id=result.get("conversation_id"),
        persisted_product_ids=result.get("persisted_product_ids") or [],
        skipped_names=result.get("skipped_names") or [],
        step_results={
            k: StepResultSummary(**v) for k, v in result.get("step_results", {}).items()
        },
        error=result.get("error"),
    )
