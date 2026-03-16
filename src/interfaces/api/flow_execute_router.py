"""
Endpoint para ejecutar Flows automáticamente.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.flow_execute_dto import ExecuteFlowRequest, ExecuteFlowResponse, StepResultSummary
from app.use_cases.flow_execute import FlowExecute, FlowNotFoundError, FlowAlreadyRunningError, FlowQuotaExceededError
from interfaces.dependencies.flow_execute_dependencies import get_flow_execute
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/flows", tags=["Flow Execution"])


@router.post("/execute", response_model=ExecuteFlowResponse)
async def execute_flow(
    body: ExecuteFlowRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: FlowExecute = Depends(get_flow_execute),
    session: AsyncSession = Depends(get_session),
):
    from domain.entities.flow import Flow
    from domain.entities.organization import Organization
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # Cargar flow para obtener org_id
    flow_stmt = select(Flow).where(Flow.id == body.flow_id)
    flow_result = await session.execute(flow_stmt)
    flow_obj = flow_result.scalar_one_or_none()

    organization = None
    plan = None

    if flow_obj:
        org_stmt = (
            select(Organization)
            .options(selectinload(Organization.plan))
            .where(Organization.id == flow_obj.organization_id)
        )
        org_result = await session.execute(org_stmt)
        organization = org_result.scalar_one_or_none()
        plan = organization.plan if organization else None

    try:
        result = await use_case.execute(
            flow_id=body.flow_id,
            context=body.context,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando Flow: {str(e)}",
        )

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