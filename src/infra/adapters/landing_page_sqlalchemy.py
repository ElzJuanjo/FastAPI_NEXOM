from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.landing_page import LandingPage, LandingPageSection
from domain.repositories.landing_page_repository import LandingPageRepository


class LandingPageSQLAlchemyRepository(LandingPageRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, lp_id: str) -> Optional[LandingPage]:
        stmt = (
            select(LandingPage)
            .options(selectinload(LandingPage.sections))
            .where(LandingPage.id == lp_id, LandingPage.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_brand(self, brand_id: str) -> List[LandingPage]:
        stmt = (
            select(LandingPage)
            .options(selectinload(LandingPage.sections))
            .where(LandingPage.brand_id == brand_id, LandingPage.deleted_at.is_(None))
            .order_by(LandingPage.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_organization(self, org_id: str, brand_id: str | None = None) -> List[LandingPage]:
        """List landing pages by organization, optionally filtered by brand."""
        stmt = (
            select(LandingPage)
            .options(selectinload(LandingPage.sections))
            .where(
                LandingPage.organization_id == org_id,
                LandingPage.deleted_at.is_(None),
            )
        )

        if brand_id:
            stmt = stmt.where(LandingPage.brand_id == brand_id)

        stmt = stmt.order_by(LandingPage.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def create(self, lp: LandingPage) -> LandingPage:
        self._session.add(lp)
        await self._session.flush()
        return lp

    async def update(self, lp: LandingPage) -> LandingPage:
        await self._session.flush()
        return lp

    async def soft_delete(self, lp_id: str) -> None:
        """Hard delete landing page and its sections."""
        from sqlalchemy import delete as sa_delete
        # Delete sections first (cascade should handle it, but be explicit)
        await self._session.execute(
            sa_delete(LandingPageSection).where(LandingPageSection.landing_page_id == lp_id)
        )
        await self._session.execute(
            sa_delete(LandingPage).where(LandingPage.id == lp_id)
        )
        await self._session.flush()

    async def add_section(self, section: LandingPageSection) -> LandingPageSection:
        self._session.add(section)
        await self._session.flush()
        return section

    async def update_section(self, section: LandingPageSection) -> LandingPageSection:
        await self._session.flush()
        return section

    async def get_section_by_id(self, section_id: str) -> Optional[LandingPageSection]:
        stmt = select(LandingPageSection).where(
            LandingPageSection.id == section_id,
            LandingPageSection.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()