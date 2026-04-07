"""
Dependencias de inyección para Brand.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository
from domain.repositories.brand_repository import BrandRepository
from app.use_cases.brand.crud import BrandCreate, BrandList, BrandUpdate, BrandDelete


def get_brand_repository(session: AsyncSession = Depends(get_session)) -> BrandRepository:
    return BrandSQLAlchemyRepository(session)


def get_brand_create(repo: BrandRepository = Depends(get_brand_repository)) -> BrandCreate:
    return BrandCreate(repo)


def get_brand_list(repo: BrandRepository = Depends(get_brand_repository)) -> BrandList:
    return BrandList(repo)


def get_brand_update(repo: BrandRepository = Depends(get_brand_repository)) -> BrandUpdate:
    return BrandUpdate(repo)


def get_brand_delete(repo: BrandRepository = Depends(get_brand_repository)) -> BrandDelete:
    return BrandDelete(repo)