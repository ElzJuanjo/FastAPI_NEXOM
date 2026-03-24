"""
Endpoints para generación masiva de creativos y gestión de galerías.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
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
from domain.entities.creative import Creative
from domain.entities.base import FlowStatus
from app.dto.creative_dto import CreativeBatchResponse, CreativeBatchListResponse, CreativeBatchRequest, CreateGalleryRequest, UpdateGalleryRequest, MoveCreativeRequest
from app.use_cases.creative_persist import persist_multiple_creatives

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/creative-batches", tags=["Creative Batches"])


# ── Presets ──────────────────────────────────────────────────────────────────

@router.get("/presets")
async def get_presets(user_id: str = Depends(get_current_user_id)):
    return {"presets": list_presets()}


# ── Create empty gallery ─────────────────────────────────────────────────────

@router.post("/gallery", response_model=CreativeBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_gallery(
    body: CreateGalleryRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Crea una galería vacía."""
    # Validar nombre único en la org
    existing = await _find_batch_by_name(session, org_id, body.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una galería con el nombre '{body.name}'.")

    batch = CreativeBatch(
        organization_id=org_id,
        product_id=body.product_id,
        name=body.name,
        status=FlowStatus.COMPLETED,
        total_expected=0,
        total_generated=0,
    )
    session.add(batch)
    await session.commit()

    stmt = select(CreativeBatch).options(selectinload(CreativeBatch.creatives)).where(CreativeBatch.id == batch.id)
    result = await session.execute(stmt)
    batch = result.scalar_one()
    return CreativeBatchResponse.model_validate(batch)


# ── Update gallery ───────────────────────────────────────────────────────────

@router.patch("/{batch_id}", response_model=CreativeBatchResponse)
async def update_gallery(
    batch_id: str,
    body: UpdateGalleryRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Edita nombre o producto de una galería."""
    stmt = select(CreativeBatch).options(selectinload(CreativeBatch.creatives)).where(
        CreativeBatch.id == batch_id, CreativeBatch.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Galería no encontrada")

    if body.name is not None and body.name != batch.name:
        existing = await _find_batch_by_name(session, org_id, body.name)
        if existing and existing.id != batch_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una galería con el nombre '{body.name}'.")
        batch.name = body.name

    if body.product_id is not None:
        batch.product_id = body.product_id or None

    await session.commit()
    await session.refresh(batch)
    return CreativeBatchResponse.model_validate(batch)


# ── Move creative to gallery ────────────────────────────────────────────────

@router.patch("/move-creative/{creative_id}")
async def move_creative_to_gallery(
    creative_id: str,
    body: MoveCreativeRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Mueve un creativo a otra galería, o lo desasocia (batch_id=null)."""
    stmt = select(Creative).where(Creative.id == creative_id, Creative.deleted_at.is_(None))
    result = await session.execute(stmt)
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creativo no encontrado")

    if body.batch_id:
        batch_stmt = select(CreativeBatch).where(CreativeBatch.id == body.batch_id, CreativeBatch.deleted_at.is_(None))
        batch_result = await session.execute(batch_stmt)
        if not batch_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Galería destino no encontrada")

    creative.batch_id = body.batch_id
    await session.commit()

    return {"message": "ok", "creative_id": creative_id, "batch_id": body.batch_id}


# ── Generate batch ───────────────────────────────────────────────────────────

@router.post("", response_model=CreativeBatchResponse)
@limiter.limit("3/minute")
async def generate_creative_batch(
    request: Request,
    body: CreativeBatchRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Genera creativos y los agrupa en una galería. Si gallery_name existe, acumula ahí."""
    plan = organization.plan
    org_id = str(organization.id)

    preset = BATCH_PRESETS.get(body.preset_id, BATCH_PRESETS["starter"])
    total_images = preset["count"]
    credits_needed = total_images * get_credit_cost("image_gen")
    remaining = plan.max_credits_per_month - organization.credits_used_this_month

    if remaining < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Créditos insuficientes: necesitas {credits_needed}, te quedan {remaining}.",
        )

    # Determinar nombre de galería
    gallery_name = body.gallery_name or body.product_name

    # Buscar galería existente o crear nueva
    batch = await _find_batch_by_name(session, org_id, gallery_name)

    if not batch:
        batch = CreativeBatch(
            organization_id=org_id,
            product_id=body.product_id,
            name=gallery_name,
            status=FlowStatus.RUNNING,
            total_expected=total_images,
            config={
                "product_description": body.product_description,
                "brand_palette": body.brand_palette,
            },
        )
        session.add(batch)
        await session.flush()
    else:
        batch.status = FlowStatus.RUNNING
        batch.total_expected = (batch.total_expected or 0) + total_images
        # Actualizar config con la última descripción
        existing_config = batch.config or {}
        existing_config["product_description"] = body.product_description
        if body.brand_palette:
            existing_config["brand_palette"] = body.brand_palette
        batch.config = existing_config
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(batch, "config")
        await session.flush()

    # Ejecutar generación (medir duración)
    import time
    batch_start_time = time.time()

    try:
        batch_result = await execute_creative_batch(
            product_name=body.product_name,
            product_description=body.product_description,
            brand_palette=body.brand_palette,
            preset_id=body.preset_id,
        )
    except Exception as e:
        batch.status = FlowStatus.ERROR
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Error generando batch: {str(e)}")

    batch_duration_ms = int((time.time() - batch_start_time) * 1000)

    # Persistir imágenes
    images_data = batch_result.get("images", [])
    creatives = []
    if images_data:
        creatives = await persist_multiple_creatives(
            session=session,
            images=images_data,
            org_id=org_id,
            product_id=body.product_id,
        )
        for creative in creatives:
            creative.batch_id = batch.id

    # Actualizar batch
    new_generated = batch_result.get("total_generated", len(creatives))
    new_failed = batch_result.get("total_failed", 0)
    new_credits = batch_result.get("credits_consumed", 0)

    batch.total_generated = (batch.total_generated or 0) + new_generated
    batch.total_failed = (batch.total_failed or 0) + new_failed
    batch.credits_consumed = (batch.credits_consumed or 0) + new_credits
    batch.status = FlowStatus.COMPLETED if new_generated > 0 else FlowStatus.ERROR

    # Cobrar créditos
    organization.credits_used_this_month += new_credits

    # Registrar en agent_tasks
    from domain.entities.agent import AgentTask
    from datetime import datetime, timezone

    if new_generated == 0:
        task_status = "error"
        task_error = f"Todas las {total_images} imágenes fallaron"
    elif new_failed > 0:
        task_status = "partial"
        task_error = f"{new_failed} de {total_images} imágenes fallaron"
    else:
        task_status = "completed"
        task_error = None

    success_pct = round((new_generated / total_images) * 100, 1) if total_images > 0 else 0

    try:
        agent_task = AgentTask(
            organization_id=org_id,
            agent_type="image_gen",
            status=task_status,
            input_payload={
                "batch_id": batch.id,
                "batch_name": gallery_name,
                "product_description": body.product_description,
                "total_requested": total_images,
            },
            output_payload={
                "content": f"Batch '{gallery_name}': {new_generated}/{total_images} imágenes generadas",
                "batch_id": batch.id,
                "total_generated": new_generated,
                "total_failed": new_failed,
                "success_pct": success_pct,
            },
            error_message=task_error,
            credits_used=new_credits,
            duration_ms=batch_duration_ms,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        session.add(agent_task)
    except Exception as e:
        logger.error(f"Error registering batch task: {e}")

    await session.commit()

    # Recargar con creativos
    stmt = select(CreativeBatch).options(selectinload(CreativeBatch.creatives)).where(CreativeBatch.id == batch.id)
    result = await session.execute(stmt)
    batch = result.scalar_one()

    return CreativeBatchResponse.model_validate(batch)


# ── List galleries ───────────────────────────────────────────────────────────

@router.get("", response_model=CreativeBatchListResponse)
async def list_batches(
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(CreativeBatch)
        .options(selectinload(CreativeBatch.creatives))
        .where(CreativeBatch.organization_id == org_id, CreativeBatch.deleted_at.is_(None))
        .order_by(CreativeBatch.created_at.desc())
    )
    result = await session.execute(stmt)
    batches = list(result.scalars().all())
    return CreativeBatchListResponse(batches=[CreativeBatchResponse.model_validate(b) for b in batches])


# ── Delete gallery ───────────────────────────────────────────────────────────

@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    from infra.tools.s3_client import delete_s3_object

    stmt = select(CreativeBatch).options(selectinload(CreativeBatch.creatives)).where(CreativeBatch.id == batch_id)
    result = await session.execute(stmt)
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Galería no encontrada")

    for creative in batch.creatives:
        s3_key = creative.s3_key
        if not s3_key and creative.file_url and ".amazonaws.com/" in creative.file_url:
            try:
                s3_key = creative.file_url.split(".amazonaws.com/", 1)[1]
            except (IndexError, AttributeError):
                pass
        if s3_key:
            await delete_s3_object(s3_key)

    await session.delete(batch)
    await session.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _find_batch_by_name(session: AsyncSession, org_id: str, name: str) -> CreativeBatch | None:
    stmt = select(CreativeBatch).where(
        CreativeBatch.organization_id == org_id,
        CreativeBatch.name == name,
        CreativeBatch.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()