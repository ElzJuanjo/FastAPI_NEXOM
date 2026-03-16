"""
Endpoint del orquestador — punto de entrada principal de NexOS.
El usuario habla con el orquestador, y este decide qué agente usar.
Valida cuota de créditos y registra consumo.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

from app.dto.orchestrator_dto import OrchestratorRequest, OrchestratorResponse
from app.orchestration.orchestrator import run_orchestrator
from app.agents.credit_costs import get_credit_cost, ROUTER_CREDIT_COST
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("", response_model=OrchestratorResponse)
@limiter.limit("10/minute")
async def orchestrate(
    request: Request,
    body: OrchestratorRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    organization = None
    plan = None

    # Cargar org y plan si se proporcionó org_id
    if body.org_id:
        from domain.entities.organization import Organization

        stmt = (
            select(Organization)
            .options(selectinload(Organization.plan))
            .where(Organization.id == body.org_id)
        )
        result = await session.execute(stmt)
        organization = result.scalar_one_or_none()
        plan = organization.plan if organization else None

        # Validar cuota mínima (router + agente más barato)
        if organization and plan:
            min_cost = ROUTER_CREDIT_COST + 1  # mínimo posible
            remaining = plan.max_credits_per_month - organization.credits_used_this_month
            if remaining < min_cost:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Créditos insuficientes: te quedan {remaining}/{plan.max_credits_per_month}. "
                           f"Actualiza tu plan para continuar.",
                )

    try:
        result = await run_orchestrator(
            user_input=body.user_input,
            context=body.context,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el orquestador: {str(e)}",
        )

    # Cobrar créditos: router + agente usado
    if organization:
        agent_type = result.get("selected_agent", "general_assistant")
        total_credits = ROUTER_CREDIT_COST + get_credit_cost(agent_type)
        organization.credits_used_this_month += total_credits
        result["credits_consumed"] = total_credits
        result["credits_remaining"] = max(0, plan.max_credits_per_month - organization.credits_used_this_month) if plan else None
        await session.commit()

    return OrchestratorResponse(**result)