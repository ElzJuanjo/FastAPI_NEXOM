"""
Dependencias de inyección para CopyAsset.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.copy_asset_sqlalchemy import CopyAssetSQLAlchemyRepository
from domain.repositories.copy_asset_repository import CopyAssetRepository
from app.use_cases.copy_asset_crud import CopyAssetCreate, CopyAssetList, CopyAssetUpdate, CopyAssetDelete


def get_copy_asset_repository(session: AsyncSession = Depends(get_session)) -> CopyAssetRepository:
    return CopyAssetSQLAlchemyRepository(session)


def get_copy_asset_create(repo: CopyAssetRepository = Depends(get_copy_asset_repository)) -> CopyAssetCreate:
    return CopyAssetCreate(repo)


def get_copy_asset_list(repo: CopyAssetRepository = Depends(get_copy_asset_repository)) -> CopyAssetList:
    return CopyAssetList(repo)


def get_copy_asset_update(repo: CopyAssetRepository = Depends(get_copy_asset_repository)) -> CopyAssetUpdate:
    return CopyAssetUpdate(repo)


def get_copy_asset_delete(repo: CopyAssetRepository = Depends(get_copy_asset_repository)) -> CopyAssetDelete:
    return CopyAssetDelete(repo)