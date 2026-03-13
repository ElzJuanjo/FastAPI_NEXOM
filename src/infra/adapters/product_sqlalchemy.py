"""
Implementación SQLAlchemy async del ProductRepository.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.product import Product
from domain.repositories.product_repository import ProductRepository


class ProductSQLAlchemyRepository(ProductRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        stmt = (
            select(Product)
            .options(selectinload(Product.brand))
            .where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: str) -> List[Product]:
        stmt = (
            select(Product)
            .options(selectinload(Product.brand))
            .where(Product.organization_id == org_id, Product.deleted_at.is_(None))
            .order_by(Product.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_brand(self, brand_id: str) -> List[Product]:
        stmt = (
            select(Product)
            .where(Product.brand_id == brand_id, Product.deleted_at.is_(None))
            .order_by(Product.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        return product

    async def update(self, product: Product) -> Product:
        await self._session.flush()
        return product

    async def soft_delete(self, product_id: str) -> None:
        stmt = select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            product.deleted_at = datetime.now(timezone.utc)
            await self._session.flush()