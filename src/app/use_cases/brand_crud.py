"""
Casos de uso CRUD para Brand.
"""

from typing import Optional, List

from domain.entities.brand import Brand
from domain.entities.base import AssetStatus
from domain.repositories.brand_repository import BrandRepository


class BrandNotFoundError(Exception):
    pass


class BrandCreate:

    def __init__(self, brand_repo: BrandRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(self, org_id: str, **kwargs) -> Brand:
        brand = Brand(
            organization_id=org_id,
            status=AssetStatus.DRAFT,
            **kwargs,
        )
        return await self._brand_repo.create(brand)


class BrandList:

    def __init__(self, brand_repo: BrandRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(self, org_id: str) -> List[Brand]:
        return await self._brand_repo.list_by_organization(org_id)


class BrandUpdate:

    def __init__(self, brand_repo: BrandRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(self, brand_id: str, **kwargs) -> Brand:
        brand = await self._brand_repo.get_by_id(brand_id)
        if not brand:
            raise BrandNotFoundError(f"Brand {brand_id} no encontrada")

        for key, value in kwargs.items():
            if value is not None:
                setattr(brand, key, value)

        return await self._brand_repo.update(brand)


class BrandDelete:

    def __init__(self, brand_repo: BrandRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(self, brand_id: str) -> None:
        brand = await self._brand_repo.get_by_id(brand_id)
        if not brand:
            raise BrandNotFoundError(f"Brand {brand_id} no encontrada")
        await self._brand_repo.soft_delete(brand_id)