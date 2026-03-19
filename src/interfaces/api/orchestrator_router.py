"""
Endpoint del orquestador — punto de entrada principal de NexOS.
El usuario habla con el orquestador, y este decide qué agente usar.
Valida cuota de créditos y registra consumo.
La organización se infiere del usuario autenticado.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

from app.dto.orchestrator_dto import OrchestratorRequest, OrchestratorResponse
from app.orchestration.orchestrator import run_orchestrator
from app.agents.credit_costs import get_credit_cost, ROUTER_CREDIT_COST
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org
from domain.entities.organization import Organization

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("", response_model=OrchestratorResponse)
@limiter.limit("10/minute")
async def orchestrate(
    request: Request,
    body: OrchestratorRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    plan = organization.plan

    # Validar cuota mínima (router + agente más barato)
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
            force_agent=body.force_agent,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el orquestador: {str(e)}",
        )

    # Cobrar créditos: router + agente usado
    agent_type = result.get("selected_agent", "general_assistant")
    total_credits = ROUTER_CREDIT_COST + get_credit_cost(agent_type)
    organization.credits_used_this_month += total_credits
    result["credits_consumed"] = total_credits
    result["credits_remaining"] = max(0, plan.max_credits_per_month - organization.credits_used_this_month)
    await session.commit()

    # Normalizar imágenes: pueden venir como strings o como dicts
    raw_images = result.get("images")
    if raw_images and isinstance(raw_images, list):
        normalized = []
        for img in raw_images:
            if isinstance(img, str):
                normalized.append(img)
            elif isinstance(img, dict):
                url = img.get("image_url", {}).get("url") or img.get("url", "")
                if url:
                    normalized.append(url)
        result["images"] = normalized

    return OrchestratorResponse(**result)