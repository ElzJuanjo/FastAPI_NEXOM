"""
Endpoints para generación masiva de creativos publicitarios.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

from app.use_cases.creative_batch import (
    list_presets, execute_creative_batch, BATCH_PRESETS,
)
from app.agents.credit_costs import get_credit_cost
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org
from domain.entities.organization import Organization

router = APIRouter(prefix="/creative-batches", tags=["Creative Batches"])


class CreativeBatchRequest(BaseModel):
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


@router.post("")
@limiter.limit("3/minute")
async def generate_creative_batch(
    request: Request,
    body: CreativeBatchRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Genera un batch de creativos publicitarios."""
    plan = organization.plan

    # Calcular créditos necesarios
    preset = BATCH_PRESETS.get(body.preset_id, BATCH_PRESETS["starter"])
    total_images = preset["total_images"]
    credits_needed = total_images * get_credit_cost("image_gen")
    remaining = plan.max_credits_per_month - organization.credits_used_this_month

    if remaining < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Créditos insuficientes: necesitas {credits_needed}, te quedan {remaining}.",
        )

    # Ejecutar batch
    batch_result = await execute_creative_batch(
        product_name=body.product_name,
        product_description=body.product_description,
        brand_palette=body.brand_palette,
        preset_id=body.preset_id,
        custom_angles=body.custom_angles,
        custom_formats=body.custom_formats,
        custom_styles=body.custom_styles,
    )

    # Cobrar créditos
    credits_consumed = batch_result.get("credits_consumed", 0)
    organization.credits_used_this_month += credits_consumed
    await session.commit()

    batch_result["credits_remaining"] = max(0, plan.max_credits_per_month - organization.credits_used_this_month)

    return batch_result
