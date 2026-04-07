from typing import List
from domain.entities.creative import Creative
from domain.entities.base import AssetStatus
from domain.repositories.creative_repository import CreativeRepository


class CreativeNotFoundError(Exception):
    pass


class CreativeCreate:
    def __init__(self, repo: CreativeRepository) -> None:
        self._repo = repo

    async def execute(self, **kwargs) -> Creative:
        creative = Creative(status=AssetStatus.PENDING, **kwargs)
        return await self._repo.create(creative)


class CreativeList:
    def __init__(self, repo: CreativeRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: str) -> List[Creative]:
        return await self._repo.list_by_product(product_id)


class CreativeUpdate:
    def __init__(self, repo: CreativeRepository) -> None:
        self._repo = repo

    async def execute(self, creative_id: str, **kwargs) -> Creative:
        creative = await self._repo.get_by_id(creative_id)
        if not creative:
            raise CreativeNotFoundError(f"Creative {creative_id} no encontrado")
        for k, v in kwargs.items():
            if v is not None:
                setattr(creative, k, v)
        return await self._repo.update(creative)


class CreativeDelete:
    def __init__(self, repo: CreativeRepository) -> None:
        self._repo = repo

    async def execute(self, creative_id: str) -> None:
        creative = await self._repo.get_by_id(creative_id)
        if not creative:
            raise CreativeNotFoundError(f"Creative {creative_id} no encontrado")
        await self._repo.soft_delete(creative_id)