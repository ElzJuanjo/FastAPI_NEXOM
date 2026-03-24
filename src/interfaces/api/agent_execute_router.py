"""
Endpoint para ejecutar agentes.
Los agentes son globales — se identifican por agent_type.
La organización se infiere del usuario autenticado.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.agent_execute_dto import ExecuteAgentRequest, ExecuteAgentResponse
from app.use_cases.agent_execute import (
    AgentExecute, AgentNotAvailableError, OrganizationQuotaExceededError,
)
from interfaces.dependencies.agent_execute_dependencies import get_agent_execute
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org
from domain.entities.organization import Organization

from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agent Execution"])


@router.post("/execute", response_model=ExecuteAgentResponse)
@limiter.limit("10/minute")
async def execute_agent(
    request: Request,
    body: ExecuteAgentRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    use_case: AgentExecute = Depends(get_agent_execute),
    session: AsyncSession = Depends(get_session),
):
    """Ejecuta un agente global y retorna el resultado."""
    plan = organization.plan

    try:
        task = await use_case.execute(
            agent_type=body.agent_type,
            user_input=body.user_input,
            organization_id=organization.id,
            context=body.context,
            organization=organization,
            plan=plan,
        )
    except OrganizationQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except AgentNotAvailableError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()

    content = None
    model = None
    if task.output_payload:
        content = task.output_payload.get("content")
        model = task.output_payload.get("model")
        
    # Persistir imágenes en S3 y crear Creatives si hay product_id
    images = task.output_payload.get("images") if task.output_payload else None
    if images and isinstance(images, list):
        from infra.tools.s3_client import upload_multiple_base64_images

        base64_imgs = []
        for img in images:
            if isinstance(img, str) and (img.startswith("data:") or len(img) > 500):
                base64_imgs.append(img)
            elif isinstance(img, dict):
                url = img.get("image_url", {}).get("url") or img.get("url", "")
                if url and (url.startswith("data:") or len(url) > 500):
                    base64_imgs.append(url)

        if base64_imgs:
            try:
                s3_results = await upload_multiple_base64_images(
                    base64_imgs, org_id=str(organization.id)
                )
                s3_urls = [r["url"] for r in s3_results]

                # Actualizar task en BD con URLs de S3
                if task.output_payload:
                    task.output_payload["images"] = s3_urls

                # Crear Creatives (con o sin product_id)
                product_id = (body.context or {}).get("product_id") or None
                from app.use_cases.creative_persist import persist_creative
                gen_params = task.output_payload.get("generation_params") or {}
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
                        logging.getLogger(__name__).error(f"Error creating creative: {e}")
                await session.commit()
                
            except Exception as e:
                logging.getLogger(__name__).error(f"Error S3 upload: {e}")

    return ExecuteAgentResponse(
        task_id=task.id,
        agent_type=task.agent_type,
        status=task.status,
        content=content,
        error_message=task.error_message,
        credits_used=task.credits_used,
        duration_ms=task.duration_ms,
        model=model,
        scraped_sources=task.output_payload.get("scraped_sources") if task.output_payload else None,
        images=task.output_payload.get("images") if task.output_payload else None,
        image_count=task.output_payload.get("image_count") if task.output_payload else None,
        created_at=task.created_at,
    )
