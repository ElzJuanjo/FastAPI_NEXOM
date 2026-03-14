from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.creative import Creative
from domain.repositories.creative_repository import CreativeRepository


class CreativeSQLAlchemyRepository(CreativeRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, creative_id: str) -> Optional[Creative]:
        stmt = select(Creative).where(Creative.id == creative_id, Creative.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_product(self, product_id: str) -> List[Creative]:
        stmt = (
            select(Creative)
            .where(Creative.product_id == product_id, Creative.deleted_at.is_(None))
            .order_by(Creative.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, creative: Creative) -> Creative:
        self._session.add(creative)
        await self._session.flush()
        return creative

    async def update(self, creative: Creative) -> Creative:
        await self._session.flush()
        return creative

    async def soft_delete(self, creative_id: str) -> None:
        stmt = select(Creative).where(Creative.id == creative_id, Creative.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        creative = result.scalar_one_or_none()
        if creative:
            creative.deleted_at = datetime.now(timezone.utc)
            await self._session.flush()