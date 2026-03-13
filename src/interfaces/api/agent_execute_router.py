"""
Endpoint para ejecutar agentes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.agent_execute_dto import ExecuteAgentRequest, ExecuteAgentResponse
from app.use_cases.agent_execute import (
    AgentExecute, AgentNotAvailableError,
    AgentConfigNotFoundError, AgentDisabledError,
)
from interfaces.dependencies.agent_execute_dependencies import get_agent_execute
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/agents", tags=["Agent Execution"])


@router.post("/execute", response_model=ExecuteAgentResponse)
async def execute_agent(
    body: ExecuteAgentRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: AgentExecute = Depends(get_agent_execute),
    session: AsyncSession = Depends(get_session),
):
    try:
        task = await use_case.execute(
            agent_config_id=body.agent_config_id,
            user_input=body.user_input,
            context=body.context,
        )
    except AgentConfigNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AgentDisabledError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AgentNotAvailableError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))

    await session.commit()

    # Construir response
    content = None
    model = None
    if task.output_payload:
        content = task.output_payload.get("content")
        model = task.output_payload.get("model")

    return ExecuteAgentResponse(
        task_id=task.id,
        status=task.status,
        content=content,
        error_message=task.error_message,
        tokens_used=task.tokens_used,
        cost_usd=task.cost_usd,
        duration_ms=task.duration_ms,
        model=model,
        created_at=task.created_at,
    )