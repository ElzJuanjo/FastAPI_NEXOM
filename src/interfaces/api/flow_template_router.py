"""
Endpoints para Flow Templates predefinidos.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from infra.adapters.flow_sqlalchemy import FlowSQLAlchemyRepository
from infra.adapters.agent_task_sqlalchemy import AgentTaskSQLAlchemyRepository
from app.dto.flow_template_dto import (
    FlowTemplateInfo, ListTemplatesResponse, CreateFlowFromTemplateRequest,
)
from app.dto.flow_dto import FlowResponse
from app.dto.flow_execute_dto import ExecuteFlowResponse, StepResultSummary
from app.use_cases.flow_template import FlowFromTemplate, FlowTemplateNotFoundError
from app.use_cases.flow_execute import FlowExecute
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id, get_current_org
from domain.entities.organization import Organization

router = APIRouter(prefix="/flow-templates", tags=["Flow Templates"])


@router.get("", response_model=ListTemplatesResponse)
async def list_templates(
    user_id: str = Depends(get_current_user_id),
):
    """Lista todos los templates de flows disponibles."""
    flow_repo = None  # No se necesita repo para listar templates
    use_case = FlowFromTemplate(flow_repo)
    templates = use_case.list_templates()
    return ListTemplatesResponse(
        templates=[FlowTemplateInfo(**t) for t in templates]
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_flow_from_template(
    body: CreateFlowFromTemplateRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Crea un Flow a partir de un template predefinido.
    Si auto_execute=true, lo ejecuta inmediatamente.
    """
    flow_repo = FlowSQLAlchemyRepository(session)
    use_case = FlowFromTemplate(flow_repo)

    try:
        flow = await use_case.create_from_template(
            org_id=org_id,
            template_id=body.template_id,
            name=body.name,
            context=body.context,
        )
    except FlowTemplateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await session.commit()

    # Recargar flow con steps
    flow = await flow_repo.get_by_id(flow.id)

    if not body.auto_execute:
        return FlowResponse.model_validate(flow)

    # Auto-ejecutar: cargar org y plan
    org_stmt = (
        select(Organization)
        .options(selectinload(Organization.plan))
        .where(Organization.id == org_id)
    )
    org_result = await session.execute(org_stmt)
    organization = org_result.scalar_one_or_none()
    plan = organization.plan if organization else None

    task_repo = AgentTaskSQLAlchemyRepository(session)
    executor = FlowExecute(flow_repo, task_repo)

    try:
        result = await executor.execute(
            flow_id=flow.id,
            context=body.context,
            organization=organization,
            plan=plan,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flow creado pero error en ejecución: {str(e)}",
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
