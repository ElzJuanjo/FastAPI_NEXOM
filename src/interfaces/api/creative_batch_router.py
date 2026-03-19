"""
Endpoints para generación masiva de creativos publicitarios.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

from app.use_cases.creative_batch import (
    list_presets, execute_creative_batch, BATCH_PRESETS,
)
from app.agents.credit_costs import get_credit_cost
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org, get_current_org_id
from domain.entities.organization import Organization
from domain.entities.creative_batch import CreativeBatch
from domain.entities.base import FlowStatus
from app.dto.creative_dto import CreativeBatchResponse, CreativeBatchListResponse, CreativeResponse
from app.use_cases.creative_persist import persist_multiple_creatives

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/creative-batches", tags=["Creative Batches"])


class CreativeBatchRequest(BaseModel):
    product_id: Optional[str] = Field(default=None, description="ID del producto para vincular creativos")
    product_name: str = Field(..., description="Nombre del producto")
    product_description: str = Field(..., description="Descripción breve del producto")
    brand_palette: Optional[str] = Field(default="", description="Colores de marca (hex)")
    preset_id: str = Field(default="starter", description="starter, campaign, full")
    custom_angles: Optional[list[str]] = None
    custom_formats: Optional[list[str]] = None
    custom_styles: Optional[list[str]] = None


@router.get("/presets")
async def get_presets(user_id: str = Depends(get_current_user_id)):
    """Lista los presets de creative batches disponibles con su costo."""
    return {"presets": list_presets()}


@router.post("", response_model=CreativeBatchResponse)
@limiter.limit("3/minute")
async def generate_creative_batch(
    request: Request,
    body: CreativeBatchRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Genera un batch de creativos publicitarios, los sube a S3 y los persiste."""
    plan = organization.plan

    # Calcular créditos
    preset = BATCH_PRESETS.get(body.preset_id, BATCH_PRESETS["starter"])
    total_images = preset["count"]
    credits_needed = total_images * get_credit_cost("image_gen")
    remaining = plan.max_credits_per_month - organization.credits_used_this_month

    if remaining < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Créditos insuficientes: necesitas {credits_needed}, te quedan {remaining}.",
        )

    # Crear registro de batch en BD
    batch = CreativeBatch(
        organization_id=str(organization.id),
        product_id=body.product_id,
        name=f"{body.product_name} — {preset['name']}",
        preset_id=body.preset_id,
        status=FlowStatus.RUNNING,
        total_expected=total_images,
        config={
            "product_name": body.product_name,
            "product_description": body.product_description,
            "brand_palette": body.brand_palette,
        },
    )
    session.add(batch)
    await session.flush()  # para obtener batch.id

    # Ejecutar generación de imágenes
    try:
        batch_result = await execute_creative_batch(
            product_name=body.product_name,
            product_description=body.product_description,
            brand_palette=body.brand_palette,
            preset_id=body.preset_id,
            custom_angles=body.custom_angles,
            custom_formats=body.custom_formats,
            custom_styles=body.custom_styles,
        )
    except Exception as e:
        batch.status = FlowStatus.ERROR
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Error generando batch: {str(e)}")

    # Persistir imágenes en S3 + BD
    images_data = batch_result.get("images", [])   
    creatives = []

    if images_data:
        creatives = await persist_multiple_creatives(
            session=session,
            images=images_data,
            org_id=str(organization.id),
            product_id=body.product_id,
        )

        # Vincular creativos al batch
        for creative in creatives:
            creative.batch_id = batch.id

    # Actualizar batch
    batch.total_generated = batch_result.get("total_generated", len(creatives))
    batch.total_failed = batch_result.get("total_failed", 0)
    batch.credits_consumed = batch_result.get("credits_consumed", 0)
    batch.status = FlowStatus.COMPLETED if batch.total_generated > 0 else FlowStatus.ERROR

    # Cobrar créditos
    organization.credits_used_this_month += batch.credits_consumed
    await session.commit()

    # Recargar batch con creativos
    stmt = (
        select(CreativeBatch)
        .options(selectinload(CreativeBatch.creatives))
        .where(CreativeBatch.id == batch.id)
    )
    result = await session.execute(stmt)
    batch = result.scalar_one()

    return CreativeBatchResponse.model_validate(batch)


@router.get("", response_model=CreativeBatchListResponse)
async def list_batches(
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Lista todos los batches de la organización."""
    stmt = (
        select(CreativeBatch)
        .options(selectinload(CreativeBatch.creatives))
        .where(CreativeBatch.organization_id == org_id)
        .where(CreativeBatch.deleted_at.is_(None))
        .order_by(CreativeBatch.created_at.desc())
    )
    result = await session.execute(stmt)
    batches = list(result.scalars().all())
    return CreativeBatchListResponse(batches=[CreativeBatchResponse.model_validate(b) for b in batches])


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Elimina un batch y todos sus creativos (S3 + BD)."""
    from infra.tools.s3_client import delete_s3_object

    stmt = (
        select(CreativeBatch)
        .options(selectinload(CreativeBatch.creatives))
        .where(CreativeBatch.id == batch_id)
    )
    result = await session.execute(stmt)
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch no encontrado")

    # Eliminar creativos de S3
    for creative in batch.creatives:
        s3_key = creative.s3_key
        if not s3_key and creative.file_url and ".amazonaws.com/" in creative.file_url:
            try:
                s3_key = creative.file_url.split(".amazonaws.com/", 1)[1]
            except (IndexError, AttributeError):
                pass
        if s3_key:
            await delete_s3_object(s3_key)

    # Hard delete batch (cascade elimina creativos)
    await session.delete(batch)
    await session.commit()