"""
Endpoints para generación masiva de creativos y gestión de galerías.
"""

import logging
import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from infra.config.database import get_session
from infra.middleware.rate_limiter import limiter
from infra.events.progress import ProgressEmitter, ProgressEvent
from starlette.requests import Request

from app.use_cases.creative.batch import (
    list_presets, execute_creative_batch, BATCH_PRESETS,
)
from app.agents.credit_costs import get_credit_cost
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org, get_current_org_id
from domain.entities.organization import Organization
from domain.entities.creative_batch import CreativeBatch
from domain.entities.creative import Creative
from domain.entities.agent import AgentTask
from domain.entities.base import FlowStatus
from app.dto.creative_dto import (
    CreativeBatchResponse, CreativeBatchListResponse, CreativeBatchRequest,
    CreateGalleryRequest, UpdateGalleryRequest, MoveCreativeRequest,
)
from app.use_cases.creative.persist import persist_multiple_creatives

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
    existing = await _find_batch_by_name(session, org_id, body.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Gallery '{body.name}' already exists.")

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
        raise HTTPException(status_code=404, detail="Gallery not found")

    if body.name is not None and body.name != batch.name:
        existing = await _find_batch_by_name(session, org_id, body.name)
        if existing and existing.id != batch_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Gallery '{body.name}' already exists.")
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
        raise HTTPException(status_code=404, detail="Creative not found")

    if body.batch_id:
        batch_stmt = select(CreativeBatch).where(CreativeBatch.id == body.batch_id, CreativeBatch.deleted_at.is_(None))
        batch_result = await session.execute(batch_stmt)
        if not batch_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Target gallery not found")

    creative.batch_id = body.batch_id
    await session.commit()

    return {"message": "ok", "creative_id": creative_id, "batch_id": body.batch_id}


# ── Generate batch (original sync endpoint) ─────────────────────────────────

@router.post("", response_model=CreativeBatchResponse)
@limiter.limit("3/minute")
async def generate_creative_batch(
    request: Request,
    body: CreativeBatchRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Genera creativos y los agrupa en una galería (sin streaming)."""
    plan = organization.plan
    org_id = str(organization.id)

    preset = BATCH_PRESETS.get(body.preset_id, BATCH_PRESETS["starter"])
    total_images = preset["count"]
    credits_needed = total_images * get_credit_cost("image_gen")
    remaining = plan.max_credits_per_month - organization.credits_used_this_month

    if remaining < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Insufficient credits: need {credits_needed}, remaining {remaining}.",
        )

    gallery_name = body.gallery_name or body.product_name
    batch = await _find_or_create_batch(session, org_id, gallery_name, body, total_images)

    batch_start_time = time.time()

    try:
        batch_result = await execute_creative_batch(
            product_name=body.product_name,
            product_description=body.product_description,
            brand_palette=body.brand_palette,
            preset_id=body.preset_id,
            product_image_url=body.product_image_url or "",
        )
    except Exception as e:
        batch.status = FlowStatus.ERROR
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Batch generation error: {str(e)}")

    batch_duration_ms = int((time.time() - batch_start_time) * 1000)

    # Persist and finalize
    await _finalize_batch(
        session=session,
        batch=batch,
        batch_result=batch_result,
        organization=organization,
        org_id=org_id,
        product_id=body.product_id,
        gallery_name=gallery_name,
        total_images=total_images,
        batch_duration_ms=batch_duration_ms,
    )

    # Reload with creatives
    stmt = select(CreativeBatch).options(selectinload(CreativeBatch.creatives)).where(CreativeBatch.id == batch.id)
    result = await session.execute(stmt)
    batch = result.scalar_one()

    return CreativeBatchResponse.model_validate(batch)


# ── Generate batch with SSE streaming ────────────────────────────────────────

@router.post("/stream")
@limiter.limit("3/minute")
async def generate_creative_batch_stream(
    request: Request,
    body: CreativeBatchRequest,
    organization: Organization = Depends(get_current_org),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Genera creativos con streaming SSE de progreso imagen por imagen."""
    plan = organization.plan
    org_id = str(organization.id)

    preset = BATCH_PRESETS.get(body.preset_id, BATCH_PRESETS["starter"])
    total_images = preset["count"]
    credits_needed = total_images * get_credit_cost("image_gen")
    remaining = plan.max_credits_per_month - organization.credits_used_this_month

    if remaining < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Insufficient credits: need {credits_needed}, remaining {remaining}.",
        )

    emitter = ProgressEmitter()

    async def stream_generator():
        batch_start_time = time.time()

        try:
            # ── Step 1: Setup gallery ──────────────────────────────────
            yield emitter.to_sse(ProgressEvent(
                stage="starting", pct=5,
                message="Preparing batch generation...",
            ))

            gallery_name = body.gallery_name or body.product_name
            batch = await _find_or_create_batch(session, org_id, gallery_name, body, total_images)

            # ── Step 2: Generate images (with real-time progress) ──────
            result_holder = {}
            error_holder = {}

            async def run_batch():
                try:
                    r = await execute_creative_batch(
                        product_name=body.product_name,
                        product_description=body.product_description,
                        brand_palette=body.brand_palette,
                        preset_id=body.preset_id,
                        product_image_url=body.product_image_url or "",
                        progress_emitter=emitter,
                    )
                    result_holder["data"] = r
                except Exception as e:
                    error_holder["error"] = str(e)
                finally:
                    await emitter.done()

            # Start generation in background, stream events as they come
            batch_task = asyncio.create_task(run_batch())

            async for event in emitter:
                yield emitter.to_sse(event)

            await batch_task

            if error_holder:
                batch.status = FlowStatus.ERROR
                await session.commit()
                yield emitter.to_sse_error(error_holder["error"])
                return

            batch_result = result_holder.get("data", {})

            # ── Step 3: Persist images to S3 ───────────────────────────
            yield emitter.to_sse(ProgressEvent(
                stage="uploading", pct=90,
                message="Saving images to storage...",
            ))

            batch_duration_ms = int((time.time() - batch_start_time) * 1000)

            await _finalize_batch(
                session=session,
                batch=batch,
                batch_result=batch_result,
                organization=organization,
                org_id=org_id,
                product_id=body.product_id,
                gallery_name=gallery_name,
                total_images=total_images,
                batch_duration_ms=batch_duration_ms,
            )

            # ── Step 4: Build final response ───────────────────────────
            yield emitter.to_sse(ProgressEvent(
                stage="saving", pct=97,
                message="Finalizing...",
            ))

            # Reload with creatives
            stmt = (
                select(CreativeBatch)
                .options(selectinload(CreativeBatch.creatives))
                .where(CreativeBatch.id == batch.id)
            )
            result = await session.execute(stmt)
            batch = result.scalar_one()

            creative_urls = [c.file_url for c in batch.creatives if c.file_url]
            new_generated = batch_result.get("total_generated", 0)
            new_failed = batch_result.get("total_failed", 0)
            new_credits = batch_result.get("credits_consumed", 0)

            done_payload = {
                "batch_id": batch.id,
                "name": batch.name,
                "total_generated": new_generated,
                "total_failed": new_failed,
                "credits_consumed": new_credits,
                "credits_remaining": max(0, plan.max_credits_per_month - organization.credits_used_this_month),
                "images": creative_urls,
                "duration_ms": int((time.time() - batch_start_time) * 1000),
                "prompt_pack": batch_result.get("prompt_pack", []),
            }

            yield emitter.to_sse_done(done_payload)

        except Exception as e:
            logger.error(f"Batch SSE stream error: {e}")
            yield emitter.to_sse_error(str(e))

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
        raise HTTPException(status_code=404, detail="Gallery not found")

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


# ── Shared helpers ───────────────────────────────────────────────────────────

async def _find_batch_by_name(session: AsyncSession, org_id: str, name: str) -> CreativeBatch | None:
    stmt = select(CreativeBatch).where(
        CreativeBatch.organization_id == org_id,
        CreativeBatch.name == name,
        CreativeBatch.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _find_or_create_batch(
    session: AsyncSession,
    org_id: str,
    gallery_name: str,
    body: CreativeBatchRequest,
    total_images: int,
) -> CreativeBatch:
    """Busca galería existente o crea una nueva."""
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
        existing_config = batch.config or {}
        existing_config["product_description"] = body.product_description
        if body.brand_palette:
            existing_config["brand_palette"] = body.brand_palette
        batch.config = existing_config
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(batch, "config")
        await session.flush()

    return batch


async def _finalize_batch(
    session: AsyncSession,
    batch: CreativeBatch,
    batch_result: dict,
    organization: Organization,
    org_id: str,
    product_id: str | None,
    gallery_name: str,
    total_images: int,
    batch_duration_ms: int,
) -> None:
    """Persiste imágenes, actualiza batch, cobra créditos, registra agent_task."""
    # Persist images
    images_data = batch_result.get("images", [])
    creatives = []
    if images_data:
        creatives = await persist_multiple_creatives(
            session=session,
            images=images_data,
            org_id=org_id,
            product_id=product_id,
        )
        for creative in creatives:
            creative.batch_id = batch.id

    # Update batch counters
    new_generated = batch_result.get("total_generated", len(creatives))
    new_failed = batch_result.get("total_failed", 0)
    new_credits = batch_result.get("credits_consumed", 0)

    batch.total_generated = (batch.total_generated or 0) + new_generated
    batch.total_failed = (batch.total_failed or 0) + new_failed
    batch.credits_consumed = (batch.credits_consumed or 0) + new_credits
    batch.status = FlowStatus.COMPLETED if new_generated > 0 else FlowStatus.ERROR

    # ── Persist prompt_pack in batch.config so it survives page reloads ──
    prompt_pack = batch_result.get("prompt_pack", [])
    if prompt_pack:
        from sqlalchemy.orm.attributes import flag_modified
        batch_config = batch.config or {}
        # Merge with existing prompt_pack (for accumulated batches)
        existing_pack = batch_config.get("prompt_pack", [])
        # Dedup by prompt text
        existing_prompts = {p["prompt"] for p in existing_pack}
        for p in prompt_pack:
            if p["prompt"] not in existing_prompts:
                existing_pack.append(p)
                existing_prompts.add(p["prompt"])
        batch_config["prompt_pack"] = existing_pack
        batch.config = batch_config
        flag_modified(batch, "config")

    # Charge credits
    organization.credits_used_this_month += new_credits

    # Register agent task
    if new_generated == 0:
        task_status = "error"
        task_error = f"All {total_images} images failed"
    elif new_failed > 0:
        task_status = "completed"
        task_error = f"{new_failed} of {total_images} images failed"
    else:
        task_status = "completed"
        task_error = None

    try:
        # ── Auto-rotate old agent tasks if near limit ──
        from app.use_cases.resource_limits import cleanup_if_needed
        await cleanup_if_needed(session, org_id, "agent_tasks")
        agent_task = AgentTask(
            organization_id=org_id,
            agent_type="image_gen",
            status=task_status,
            input_payload={
                "batch_id": batch.id,
                "batch_name": gallery_name,
                "product_description": batch.config.get("product_description", "") if batch.config else "",
                "total_requested": total_images,
            },
            output_payload={
                "content": f"Batch '{gallery_name}': {new_generated}/{total_images} images generated",
                "batch_id": batch.id,
                "total_generated": new_generated,
                "total_failed": new_failed,
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