"""
Utilidad para persistir imágenes generadas como Creatives en BD + S3.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.creative import Creative
from domain.entities.base import AssetStatus, AgentType
from infra.tools.s3_client import upload_base64_image

logger = logging.getLogger(__name__)


async def persist_creative(
    session: AsyncSession,
    base64_image: str,
    org_id: str,
    product_id: Optional[str] = None,
    style: Optional[str] = None,
    format: Optional[str] = None,
    platform: Optional[str] = None,
    angle: Optional[str] = None,
    generation_prompt: Optional[str] = None,
    generation_params: Optional[dict] = None,
) -> Creative:
    """
    Sube una imagen base64 a S3 y crea un Creative en la BD.
    Si base64_image ya es una URL http, solo crea el registro.
    """
    # ── Resource limit check ──
    from app.use_cases.resource_limits import check_resource_limit, ResourceLimitExceededError
    try:
        await check_resource_limit(session, org_id, "creatives")
    except ResourceLimitExceededError:
        logger.warning(
            f"Creative persist skipped for org {org_id}: resource limit reached"
        )
        raise

    # Si ya es URL, no re-subir, pero extraer s3_key
    if base64_image.startswith("http"):
        s3_key = None
        if ".amazonaws.com/" in base64_image:
            try:
                s3_key = base64_image.split(".amazonaws.com/", 1)[1]
            except (IndexError, AttributeError):
                pass

        creative = Creative(
            organization_id=org_id,
            product_id=product_id,
            agent_type=AgentType.IMAGE_GEN,
            style=style,
            format=format,
            platform=platform,
            angle=angle,
            status=AssetStatus.APPROVED,
            file_url=base64_image,
            s3_key=s3_key,
            generation_prompt=generation_prompt,
            generation_params=generation_params or {},
        )
        session.add(creative)
        return creative

    # Subir a S3
    s3_result = await upload_base64_image(
        base64_data=base64_image,
        org_id=org_id,
        folder="creatives",
    )

    creative = Creative(
        organization_id=org_id,
        product_id=product_id,
        agent_type=AgentType.IMAGE_GEN,
        style=style,
        format=format,
        platform=platform,
        angle=angle,
        status=AssetStatus.APPROVED,
        file_url=s3_result["url"],
        s3_key=s3_result["key"],
        file_size_bytes=s3_result["size_bytes"],
        generation_prompt=generation_prompt,
        generation_params=generation_params or {},
    )

    session.add(creative)
    logger.info(f"Creative persisted: {creative.file_url}")
    return creative


async def persist_multiple_creatives(
    session: AsyncSession,
    images: list[dict],
    org_id: str,
    product_id: Optional[str] = None,
) -> list[Creative]:
    """
    Persiste múltiples imágenes como Creatives.
    Normaliza el campo 'image' que puede venir como string base64, URL, o dict de OpenAI vision.
    """
    # ── Pre-check: cuántos slots disponibles ──
    from app.use_cases.resource_limits import count_resources, RESOURCE_LIMITS
    current_count = await count_resources(session, org_id, "creatives")
    limit = RESOURCE_LIMITS.get("creatives", 300)
    available_slots = max(0, limit - current_count)

    if available_slots == 0:
        logger.warning(
            f"Creative batch persist skipped for org {org_id}: resource limit reached ({current_count}/{limit})"
        )
        return []

    creatives = []

    for item in images[:available_slots]:  # Cap by available slots
        raw_image = item.get("image")
        if not raw_image:
            continue

        # Normalizar: puede ser string o dict OpenAI {"type": "image_url", "image_url": {"url": "data:..."}}
        if isinstance(raw_image, dict):
            base64_data = raw_image.get("image_url", {}).get("url") or raw_image.get("url", "")
        elif isinstance(raw_image, str):
            base64_data = raw_image
        else:
            logger.warning(f"Unexpected image type: {type(raw_image)}")
            continue

        if not base64_data:
            continue

        try:
            creative = await persist_creative(
                session=session,
                base64_image=base64_data,
                org_id=org_id,
                product_id=product_id,
                style=item.get("style"),
                format=item.get("aspect_ratio") or item.get("format"),
                platform=item.get("platform"),
                angle=item.get("angle"),
                generation_prompt=item.get("prompt_used"),
                generation_params={
                    "angle": item.get("angle"),
                    "model": item.get("model"),
                },
            )
            creatives.append(creative)
        except Exception as e:
            logger.error(f"Error persisting creative: {e}")

    return creatives
