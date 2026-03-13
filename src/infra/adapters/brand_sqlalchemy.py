"""
Implementación SQLAlchemy async del BrandRepository.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.brand import Brand
from domain.repositories.brand_repository import BrandRepository


class BrandSQLAlchemyRepository(BrandRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, brand_id: str) -> Optional[Brand]:
        stmt = (
            select(Brand)
            .options(selectinload(Brand.products))
            .where(Brand.id == brand_id, Brand.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: str) -> List[Brand]:
        stmt = (
            select(Brand)
            .where(Brand.organization_id == org_id, Brand.deleted_at.is_(None))
            .order_by(Brand.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, brand: Brand) -> Brand:
        self._session.add(brand)
        await self._session.flush()
        return brand

    async def update(self, brand: Brand) -> Brand:
        await self._session.flush()
        return brand

    async def soft_delete(self, brand_id: str) -> None:
        stmt = select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        brand = result.scalar_one_or_none()
        if brand:
            brand.deleted_at = datetime.now(timezone.utc)
            await self._session.flush()