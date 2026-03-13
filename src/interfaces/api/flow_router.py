"""
Endpoints de Flow y FlowStep.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.flow_dto import (
    CreateFlowRequest, UpdateFlowRequest, FlowResponse, FlowListResponse,
    CreateFlowStepRequest, UpdateFlowStepRequest, FlowStepResponse,
)
from app.use_cases.flow_crud import (
    FlowCreate, FlowList, FlowUpdate, FlowDelete,
    FlowAddStep, FlowStepUpdate,
    FlowNotFoundError, FlowStepNotFoundError,
)
from interfaces.dependencies.flow_dependencies import (
    get_flow_create, get_flow_list, get_flow_update, get_flow_delete,
    get_flow_add_step, get_flow_step_update,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/flows", tags=["Flows"])


@router.post("", response_model=FlowResponse, status_code=status.HTTP_201_CREATED)
async def create_flow(
    body: CreateFlowRequest,
    org_id: str = Query(..., description="Organization ID"),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowCreate = Depends(get_flow_create),
    session: AsyncSession = Depends(get_session),
):
    steps_data = [s.model_dump() for s in body.steps] if body.steps else None

    flow = await use_case.execute(
        org_id=org_id,
        name=body.name,
        context=body.context,
        steps_data=steps_data,
    )
    await session.commit()

    # Recargar con steps
    from infra.adapters.flow_sqlalchemy import FlowSQLAlchemyRepository
    repo = FlowSQLAlchemyRepository(session)
    flow = await repo.get_by_id(flow.id)

    return FlowResponse.model_validate(flow)


@router.get("", response_model=FlowListResponse)
async def list_flows(
    org_id: str = Query(..., description="Organization ID"),
    user_id: str = Depends(get_current_user_id),
    use_case: FlowList = Depends(get_flow_list),
):
    flows = await use_case.execute(org_id)
    return FlowListResponse(flows=[FlowResponse.model_validate(f) for f in flows])


@router.patch("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    flow_id: str,
    body: UpdateFlowRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: FlowUpdate = Depends(get_flow_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        flow = await use_case.execute(
            flow_id=flow_id,
            **body.model_dump(exclude_unset=True),
        )
    except FlowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return FlowResponse.model_validate(flow)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: FlowDelete = Depends(get_flow_delete),
    session: AsyncSession = Depends(get_session),
):
    try:
        await use_case.execute(flow_id)
    except FlowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()


# ---------------------------------------------------------------------------
# Flow Steps
# ---------------------------------------------------------------------------

@router.post("/{flow_id}/steps", response_model=FlowStepResponse, status_code=status.HTTP_201_CREATED)
async def add_flow_step(
    flow_id: str,
    body: CreateFlowStepRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: FlowAddStep = Depends(get_flow_add_step),
    session: AsyncSession = Depends(get_session),
):
    try:
        step = await use_case.execute(
            flow_id=flow_id,
            agent_type=body.agent_type,
            name=body.name,
            order=body.order,
            depends_on_step_id=body.depends_on_step_id,
        )
    except FlowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return FlowStepResponse.model_validate(step)


@router.patch("/steps/{step_id}", response_model=FlowStepResponse)
async def update_flow_step(
    step_id: str,
    body: UpdateFlowStepRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: FlowStepUpdate = Depends(get_flow_step_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        step = await use_case.execute(
            step_id=step_id,
            **body.model_dump(exclude_unset=True),
        )
    except FlowStepNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return FlowStepResponse.model_validate(step)