"""
Casos de uso CRUD para Product.
"""

from typing import Optional, List

from domain.entities.product import Product
from domain.repositories.product_repository import ProductRepository


class ProductNotFoundError(Exception):
    pass


class ProductCreate:

    def __init__(self, product_repo: ProductRepository) -> None:
        self._product_repo = product_repo

    async def execute(self, org_id: str, **kwargs) -> Product:
        product = Product(
            organization_id=org_id,
            **kwargs,
        )
        return await self._product_repo.create(product)


class ProductList:

    def __init__(self, product_repo: ProductRepository) -> None:
        self._product_repo = product_repo

    async def execute(self, org_id: str) -> List[Product]:
        return await self._product_repo.list_by_organization(org_id)


class ProductUpdate:

    def __init__(self, product_repo: ProductRepository) -> None:
        self._product_repo = product_repo

    async def execute(self, product_id: str, **kwargs) -> Product:
        product = await self._product_repo.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(f"Product {product_id} no encontrado")

        for key, value in kwargs.items():
            if value is not None:
                setattr(product, key, value)

        return await self._product_repo.update(product)


class ProductDelete:

    def __init__(self, product_repo: ProductRepository) -> None:
        self._product_repo = product_repo

    async def execute(self, product_id: str) -> None:
        product = await self._product_repo.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(f"Product {product_id} no encontrado")
        await self._product_repo.soft_delete(product_id)