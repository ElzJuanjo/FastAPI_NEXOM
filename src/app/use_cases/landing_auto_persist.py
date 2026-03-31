"""
Auto-persistencia de secciones de Landing Page.
Se invoca cuando el agente landing_page genera contenido con estructura de landing.
Crea automáticamente un LandingPage con sus secciones en la BD.

V2 — JSON embebido:
Primary: extrae el bloque <!--LANDING_JSON {...} --> del output del agente.
Fallback: usa el parser regex original (landing_section_parser) si no hay JSON.
"""

from __future__ import annotations

import re
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.landing_page import LandingPage, LandingPageSection
from domain.entities.base import AssetStatus, LandingSectionType

logger = logging.getLogger(__name__)

# Valid section types from the enum
VALID_SECTION_TYPES = {e.value for e in LandingSectionType}


def is_landing_content(content: str) -> bool:
    """Detecta si el output del agente contiene una landing page completa."""
    if not content or len(content) < 200:
        return False

    # Fast path: JSON block present
    if "<!--LANDING_JSON" in content:
        return True

    # Heuristic fallback
    from app.use_cases.landing_section_parser import is_landing_content as _legacy_check
    return _legacy_check(content)


def _extract_landing_json(content: str) -> dict | None:
    """
    Extract the structured JSON from <!--LANDING_JSON {...} --> comment block.
    Returns parsed dict or None if not found / invalid.
    """
    match = re.search(
        r'<!--\s*LANDING_JSON\s*(\{.*?\})\s*-->',
        content,
        re.DOTALL
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if isinstance(data, dict) and isinstance(data.get("sections"), list):
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LANDING_JSON block: {e}")

    return None


def _normalize_sections(data: dict) -> list[dict]:
    """
    Normalize and validate section data from the JSON block.
    Returns list of dicts ready for LandingPageSection creation.
    """
    raw_sections = data.get("sections", [])
    if not isinstance(raw_sections, list):
        return []

    results = []
    for order, sec in enumerate(raw_sections, start=1):
        if not isinstance(sec, dict):
            continue

        section_type = sec.get("section_type", "custom")
        if section_type not in VALID_SECTION_TYPES:
            section_type = "custom"

        title = sec.get("title")
        body = sec.get("body")
        cta_text = sec.get("cta_text")
        cta_url = sec.get("cta_url")
        content = sec.get("content")

        # Validate minimal data
        if not title and not body:
            continue

        # Clean up
        if isinstance(title, str):
            title = title.strip()[:255]
        if isinstance(body, str):
            body = body.strip()
        if isinstance(cta_text, str):
            cta_text = cta_text.strip()[:255]
        if isinstance(cta_url, str):
            cta_url = cta_url.strip()[:512]
        if content and not isinstance(content, dict):
            content = None

        results.append({
            "section_type": section_type,
            "title": title,
            "body": body,
            "cta_text": cta_text,
            "cta_url": cta_url,
            "order": order,
            "is_visible": True,
            "content": content,
        })

    return results


async def auto_persist_landing_sections(
    session: AsyncSession,
    content: str,
    org_id: str,
    brand_id: str | None = None,
    conversation_id: str | None = None,
) -> str | None:
    """
    Detecta si el contenido del agente es una landing page completa,
    parsea las secciones, y las persiste en la BD.

    Primary: JSON extraction from <!--LANDING_JSON --> block.
    Fallback: regex parser (landing_section_parser).

    Returns:
        landing_page_id si se creó, None si no se detectó estructura
    """
    if not is_landing_content(content):
        return None

    # Try JSON extraction first
    json_data = _extract_landing_json(content)
    source = "json"

    if json_data:
        sections_data = _normalize_sections(json_data)
        lp_name = json_data.get("landing_name", "").strip()[:255] or None
    else:
        # Fallback to regex parser
        source = "fallback"
        logger.info("LANDING_JSON block not found, using fallback regex parser")
        from app.use_cases.landing_section_parser import parse_landing_sections
        sections_data = parse_landing_sections(content)
        lp_name = None

    if len(sections_data) < 2:
        return None

    # Landing page name: from JSON > conversation title > default
    if not lp_name:
        lp_name = "Landing — Auto-generada"
        if conversation_id:
            from domain.entities.conversation import Conversation
            from sqlalchemy import select
            stmt = select(Conversation.title).where(Conversation.id == conversation_id)
            result = await session.execute(stmt)
            conv_title = result.scalar_one_or_none()
            if conv_title:
                lp_name = conv_title[:255]

    landing_page = LandingPage(
        organization_id=org_id,
        brand_id=brand_id,
        name=lp_name,
        status=AssetStatus.DRAFT,
    )
    session.add(landing_page)
    await session.flush()

    # Create sections
    for section_data in sections_data:
        section_type_str = section_data.get("section_type", "custom")

        try:
            section_type = LandingSectionType(section_type_str)
        except ValueError:
            section_type = LandingSectionType.CUSTOM

        section = LandingPageSection(
            landing_page_id=landing_page.id,
            section_type=section_type,
            title=section_data.get("title"),
            body=section_data.get("body"),
            cta_text=section_data.get("cta_text"),
            cta_url=section_data.get("cta_url"),
            order=section_data.get("order", 1),
            is_visible=True,
            content=section_data.get("content"),
        )
        session.add(section)

    await session.flush()

    logger.info(
        f"Auto-created landing page {landing_page.id} "
        f"with {len(sections_data)} sections "
        f"(source={source}) "
        f"for org {org_id}"
    )

    return landing_page.id