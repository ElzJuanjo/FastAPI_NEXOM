from typing import Optional, List
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from domain.entities.copy_asset import CopyAsset
from domain.repositories.copy_asset_repository import CopyAssetRepository


class CopyAssetSQLAlchemyRepository(CopyAssetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, asset_id: str) -> Optional[CopyAsset]:
        stmt = select(CopyAsset).where(CopyAsset.id == asset_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        org_id: str,
        copy_type: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        brand_id: str | None = None,
    ) -> List[CopyAsset]:
        stmt = select(CopyAsset).where(CopyAsset.organization_id == org_id)
        if copy_type:
            stmt = stmt.where(CopyAsset.copy_type == copy_type)
        if platform:
            stmt = stmt.where(CopyAsset.platform == platform)
        if status:
            stmt = stmt.where(CopyAsset.status == status)
        if brand_id:
            stmt = stmt.where(CopyAsset.brand_id == brand_id)
        stmt = stmt.order_by(CopyAsset.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, asset: CopyAsset) -> CopyAsset:
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def update(self, asset: CopyAsset) -> CopyAsset:
        await self._session.flush()
        return asset

    async def delete(self, asset_id: str) -> None:
        stmt = sa_delete(CopyAsset).where(CopyAsset.id == asset_id)
        await self._session.execute(stmt)