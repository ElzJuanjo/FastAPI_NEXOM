"""
Endpoints de AgentConfig y AgentTask.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.agent_dto import (
    CreateAgentConfigRequest, UpdateAgentConfigRequest,
    AgentConfigResponse, AgentConfigListResponse,
    CreateAgentTaskRequest, AgentTaskResponse, AgentTaskListResponse,
)
from app.use_cases.agent_config_crud import (
    AgentConfigCreate, AgentConfigList, AgentConfigUpdate,
    AgentConfigAlreadyExistsError, AgentConfigNotFoundError,
)
from app.use_cases.agent_task_crud import (
    AgentTaskCreate, AgentTaskList, AgentConfigNotFoundForTaskError,
)
from interfaces.dependencies.agent_dependencies import (
    get_agent_config_create, get_agent_config_list, get_agent_config_update,
    get_agent_task_create, get_agent_task_list,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id

from interfaces.dependencies.org_membership import verify_org_membership


# ===========================================================================
# Agent Configs
# ===========================================================================

config_router = APIRouter(prefix="/agent-configs", tags=["Agent Configs"])


@config_router.post("", response_model=AgentConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_config(
    body: CreateAgentConfigRequest,
    org_id: str = Depends(verify_org_membership),
    user_id: str = Depends(get_current_user_id),
    use_case: AgentConfigCreate = Depends(get_agent_config_create),
    session: AsyncSession = Depends(get_session),
):
    try:
        config = await use_case.execute(
            org_id=org_id,
            agent_type=body.agent_type,
            ai_provider=body.ai_provider,
            model_version=body.model_version,
            is_enabled=body.is_enabled,
            config_params=body.config_params,
        )
    except AgentConfigAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await session.commit()
    return AgentConfigResponse.model_validate(config)


@config_router.get("", response_model=AgentConfigListResponse)
async def list_agent_configs(
    org_id: str = Depends(verify_org_membership),
    user_id: str = Depends(get_current_user_id),
    use_case: AgentConfigList = Depends(get_agent_config_list),
):
    configs = await use_case.execute(org_id)
    return AgentConfigListResponse(
        agent_configs=[AgentConfigResponse.model_validate(c) for c in configs]
    )


@config_router.patch("/{config_id}", response_model=AgentConfigResponse)
async def update_agent_config(
    config_id: str,
    body: UpdateAgentConfigRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: AgentConfigUpdate = Depends(get_agent_config_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        config = await use_case.execute(
            config_id=config_id,
            **body.model_dump(exclude_unset=True),
        )
    except AgentConfigNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return AgentConfigResponse.model_validate(config)


# ===========================================================================
# Agent Tasks
# ===========================================================================

task_router = APIRouter(prefix="/agent-tasks", tags=["Agent Tasks"])


@task_router.post("", response_model=AgentTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_task(
    body: CreateAgentTaskRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: AgentTaskCreate = Depends(get_agent_task_create),
    session: AsyncSession = Depends(get_session),
):
    try:
        task = await use_case.execute(
            agent_config_id=body.agent_config_id,
            input_payload=body.input_payload,
        )
    except AgentConfigNotFoundForTaskError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return AgentTaskResponse.model_validate(task)


@task_router.get("", response_model=AgentTaskListResponse)
async def list_agent_tasks(
    config_id: str = Query(..., description="AgentConfig ID"),
    limit: int = Query(default=20, le=100),
    user_id: str = Depends(get_current_user_id),
    use_case: AgentTaskList = Depends(get_agent_task_list),
):
    tasks = await use_case.execute(config_id, limit)
    return AgentTaskListResponse(
        tasks=[AgentTaskResponse.model_validate(t) for t in tasks]
    )