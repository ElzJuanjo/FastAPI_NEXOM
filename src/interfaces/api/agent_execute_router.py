"""
Endpoint para ejecutar agentes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from app.dto.agent_execute_dto import ExecuteAgentRequest, ExecuteAgentResponse
from app.use_cases.agent_execute import (
    AgentExecute, AgentConfigNotFoundError, AgentDisabledError,
    AgentNotAvailableError, OrganizationQuotaExceededError,
)
from interfaces.dependencies.agent_execute_dependencies import get_agent_execute
from interfaces.dependencies.auth_dependencies import get_current_user_id

from domain.entities.agent import AgentConfig
from domain.entities.organization import Organization

router = APIRouter(prefix="/agents", tags=["Agent Execution"])


@router.post("/execute", response_model=ExecuteAgentResponse)
async def execute_agent(
    body: ExecuteAgentRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: AgentExecute = Depends(get_agent_execute),
    session: AsyncSession = Depends(get_session),
):
    """Ejecuta un agente y retorna el resultado."""
    # Cargar config para obtener org_id
    config_stmt = select(AgentConfig).where(AgentConfig.id == body.agent_config_id)
    config_result = await session.execute(config_stmt)
    config = config_result.scalar_one_or_none()

    organization = None
    plan = None

    if config:
        # Cargar organización con plan
        org_stmt = (
            select(Organization)
            .options(selectinload(Organization.plan))
            .where(Organization.id == config.organization_id)
        )
        org_result = await session.execute(org_stmt)
        organization = org_result.scalar_one_or_none()
        plan = organization.plan if organization else None

    try:
        task = await use_case.execute(
            agent_config_id=body.agent_config_id,
            user_input=body.user_input,
            context=body.context,
            organization=organization,
            plan=plan,
        )
    except OrganizationQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except AgentConfigNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AgentDisabledError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AgentNotAvailableError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()

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
        scraped_sources=task.output_payload.get("scraped_sources") if task.output_payload else None,
        images=task.output_payload.get("images") if task.output_payload else None,
        image_count=task.output_payload.get("image_count") if task.output_payload else None,
        created_at=task.created_at,
    )