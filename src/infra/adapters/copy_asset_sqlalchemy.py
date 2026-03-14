from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.entities.copy_asset import CopyAsset
from domain.repositories.copy_asset_repository import CopyAssetRepository


class CopyAssetSQLAlchemyRepository(CopyAssetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, asset_id: str) -> Optional[CopyAsset]:
        stmt = select(CopyAsset).where(CopyAsset.id == asset_id, CopyAsset.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_brand(self, brand_id: str) -> List[CopyAsset]:
        stmt = select(CopyAsset).where(CopyAsset.brand_id == brand_id, CopyAsset.deleted_at.is_(None)).order_by(CopyAsset.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, asset: CopyAsset) -> CopyAsset:
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def update(self, asset: CopyAsset) -> CopyAsset:
        await self._session.flush()
        return asset

    async def soft_delete(self, asset_id: str) -> None:
        asset = await self.get_by_id(asset_id)
        if asset:
            asset.deleted_at = datetime.now(timezone.utc)
            await self._session.flush()