"""
Auto-persistencia de Copy Assets desde output de agentes copywriting y ads.

ESTRATEGIA: El system prompt del agente le indica que emita un bloque
<!--COPY_JSON [{...}] --> al final de su respuesta.
Este módulo extrae ese JSON array y persiste cada asset.
"""

from __future__ import annotations

import re
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.copy_asset import CopyAsset
from domain.entities.base import AssetStatus, CopyType, AdPlatform

logger = logging.getLogger(__name__)


# ── Valid enums ──────────────────────────────────────────────────────────────

VALID_COPY_TYPES = {"ad", "email", "social", "headline", "cta", "body"}
VALID_PLATFORMS = {"meta_ads", "google_ads", "tiktok_ads", "instagram", "landing_page", "email_marketing"}


# ── Detection ────────────────────────────────────────────────────────────────

def has_copy_json(content: str) -> bool:
    return bool(content and "<!--COPY_JSON" in content)


# ── JSON Extraction ──────────────────────────────────────────────────────────

def _extract_copy_json(content: str) -> list[dict] | None:
    match = re.search(
        r'<!--\s*COPY_JSON\s*(\[.*?\])\s*-->',
        content,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if isinstance(data, list) and len(data) > 0:
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse COPY_JSON block: {e}")

    return None


def _normalize_asset(item: dict) -> dict | None:
    """Validate and normalize a single copy asset dict."""
    content = item.get("content", "").strip()
    if not content or len(content) < 5:
        return None

    name = str(item.get("name", ""))[:255]
    if not name:
        name = content[:60] + ("..." if len(content) > 60 else "")

    copy_type = item.get("copy_type", "body")
    if copy_type not in VALID_COPY_TYPES:
        copy_type = "body"

    platform = item.get("platform")
    if platform and platform not in VALID_PLATFORMS:
        platform = None

    tone = item.get("tone")
    if tone and len(str(tone)) > 100:
        tone = str(tone)[:100]

    variations = item.get("variations")
    if isinstance(variations, list):
        variations = [
            {"content": str(v.get("content", v) if isinstance(v, dict) else v).strip(), "order": i + 1}
            for i, v in enumerate(variations)
            if v
        ][:10]
    else:
        variations = None

    return {
        "name": name,
        "copy_type": copy_type,
        "platform": platform,
        "tone": tone,
        "content": content,
        "variations": variations,
    }


# ── Main persist function ────────────────────────────────────────────────────

async def auto_persist_copy_assets(
    session: AsyncSession,
    content: str,
    org_id: str,
    brand_id: str | None = None,
    conversation_id: str | None = None,
) -> list[str]:
    """
    Detecta y persiste copy assets desde el output de agentes copywriting/ads.
    Returns list of created asset IDs.
    """
    if not has_copy_json(content):
        return []

    items = _extract_copy_json(content)
    if not items:
        return []

    created_ids = []
    for item in items[:20]:  # max 20 assets per response
        normalized = _normalize_asset(item)
        if not normalized:
            continue

        raw_type = normalized.pop("copy_type", "body")
        raw_platform = normalized.pop("platform", None)

        try:
            enum_type = CopyType(raw_type)
        except (ValueError, KeyError):
            enum_type = CopyType.BODY

        enum_platform = None
        if raw_platform:
            try:
                enum_platform = AdPlatform(raw_platform)
            except (ValueError, KeyError):
                enum_platform = None

        asset = CopyAsset(
            organization_id=org_id,
            brand_id=brand_id,
            product_id=None,
            status=AssetStatus.DRAFT,
            copy_type=enum_type,
            platform=enum_platform,
            **normalized,
        )
        session.add(asset)
        await session.flush()
        created_ids.append(asset.id)

    if created_ids:
        logger.info(
            f"Auto-created {len(created_ids)} copy assets "
            f"for org {org_id} from conversation {conversation_id}"
        )

    return created_ids