"""
Auto-persistencia de secciones de Landing Page.
Se invoca cuando el agente landing_page genera contenido con estructura de landing.
Crea automáticamente un LandingPage con sus secciones en la BD.
"""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.use_cases.landing_section_parser import parse_landing_sections, is_landing_content
from domain.entities.landing_page import LandingPage, LandingPageSection
from domain.entities.base import AssetStatus, LandingSectionType

logger = logging.getLogger(__name__)


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

    Args:
        session: DB session
        content: Output del agente landing_page
        org_id: Organization ID
        brand_id: Brand ID (from context, optional)
        conversation_id: For naming the landing page

    Returns:
        landing_page_id si se creó, None si no se detectó estructura
    """
    if not is_landing_content(content):
        return None

    sections_data = parse_landing_sections(content)
    if len(sections_data) < 2:
        return None

    # Use conversation title as landing name
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
        brand_id=None,
        name=lp_name,
        status=AssetStatus.DRAFT,
    )
    session.add(landing_page)
    await session.flush()

    # Create sections
    for section_data in sections_data:
        section_type_str = section_data.get("section_type", "custom")

        # Validate the section type exists in the enum
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
        f"Auto-created landing page {landing_page.id} with {len(sections_data)} sections "
        f"for org {org_id}"
    )

    return landing_page.id