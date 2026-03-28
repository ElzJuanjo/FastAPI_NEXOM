"""
Endpoints para ejecutar Flows — sync y streaming SSE.
"""

import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.events.progress import ProgressEmitter, ProgressEvent
from app.dto.flow_execute_dto import ExecuteFlowRequest, ExecuteFlowResponse, StepResultSummary
from app.use_cases.flow_execute import FlowExecute, FlowNotFoundError, FlowAlreadyRunningError, FlowQuotaExceededError
from interfaces.dependencies.flow_execute_dependencies import get_flow_execute
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org
from domain.entities.organization import Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flows", tags=["Flow Execution"])


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

    return ExecuteFlowResponse(
        flow_id=result["flow_id"],
        status=result["status"],
        total_steps=result["total_steps"],
        completed_steps=result["completed_steps"],
        total_tokens=result["total_tokens"],
        total_duration_ms=result["total_duration_ms"],
        step_results={
            k: StepResultSummary(**v) for k, v in result["step_results"].items()
        },
        error=result.get("error"),
    )


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
                }

            done_payload = {
                "flow_id": result["flow_id"],
                "status": result["status"],
                "total_steps": result["total_steps"],
                "completed_steps": result["completed_steps"],
                "total_tokens": result["total_tokens"],
                "total_duration_ms": result["total_duration_ms"],
                "credits_consumed": result.get("credits_consumed", 0),
                "credits_remaining": result.get("credits_remaining"),
                "conversation_id": result.get("conversation_id"),
                "step_results": step_results,
                "error": result.get("error"),
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