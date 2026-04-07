"""
Dependencias de inyección para Product.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.product_sqlalchemy import ProductSQLAlchemyRepository
from domain.repositories.product_repository import ProductRepository
from app.use_cases.product.crud import ProductCreate, ProductList, ProductUpdate, ProductDelete


def get_product_repository(session: AsyncSession = Depends(get_session)) -> ProductRepository:
    return ProductSQLAlchemyRepository(session)


def get_product_create(repo: ProductRepository = Depends(get_product_repository)) -> ProductCreate:
    return ProductCreate(repo)


def get_product_list(repo: ProductRepository = Depends(get_product_repository)) -> ProductList:
    return ProductList(repo)


def get_product_update(repo: ProductRepository = Depends(get_product_repository)) -> ProductUpdate:
    return ProductUpdate(repo)


def get_product_delete(repo: ProductRepository = Depends(get_product_repository)) -> ProductDelete:
    return ProductDelete(repo)