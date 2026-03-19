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

import logging
logger = logging.getLogger(__name__)

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
    
    # Registrar en agent_tasks para historial de actividad
    from domain.entities.agent import AgentTask
    from datetime import datetime, timezone

    try:
        agent_task = AgentTask(
            organization_id=str(organization.id),
            agent_type=agent_type,
            status="completed" if not result.get("error") else "error",
            input_payload={
                "user_input": body.user_input,
                "context": body.context,
                "force_agent": body.force_agent,
            },
            output_payload={
                "content": result.get("content"),
                "images": result.get("images"),
                "image_count": result.get("image_count"),
                "model": result.get("model"),
            },
            error_message=result.get("error"),
            tokens_used=result.get("tokens_used"),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=result.get("duration_ms"),
        )
        session.add(agent_task)
        await session.commit()
    except Exception as e:
        logger.error(f"Error registering orchestrator task: {e}")

    # Normalizar imágenes, subir a S3, y opcionalmente crear Creatives
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

        # Subir base64 a S3
        from infra.tools.s3_client import upload_multiple_base64_images

        base64_images = [img for img in normalized if img.startswith("data:") or len(img) > 500]

        if base64_images:
            try:
                s3_results = await upload_multiple_base64_images(
                    base64_images, org_id=str(organization.id)
                )
                s3_urls = [r["url"] for r in s3_results]
                non_base64 = [img for img in normalized if not img.startswith("data:") and len(img) <= 500]
                result["images"] = non_base64 + s3_urls

                # Crear Creatives en BD (con o sin product_id)
                product_id = (body.context or {}).get("product_id") or None
                from app.use_cases.creative_persist import persist_creative
                gen_params = result.get("generation_params") or {}
                for s3_url in s3_urls:
                    try:
                        await persist_creative(
                            session=session,
                            base64_image=s3_url,
                            org_id=str(organization.id),
                            product_id=product_id,
                            style=gen_params.get("style"),
                            format=gen_params.get("aspect_ratio"),
                            generation_prompt=gen_params.get("prompt"),
                        )
                    except Exception as e:
                        logger.error(f"Error creating creative from orchestrator: {e}")
                await session.commit()

            except Exception as e:
                logger.error(f"Error subiendo imágenes a S3: {e}")
                result["images"] = normalized
        else:
            result["images"] = normalized

    return OrchestratorResponse(**result)