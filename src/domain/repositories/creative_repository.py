from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.creative import Creative


class CreativeRepository(ABC):

    @abstractmethod
    async def get_by_id(self, creative_id: str) -> Optional[Creative]:
        ...

    @abstractmethod
    async def list_by_product(self, product_id: str) -> List[Creative]:
        ...

    @abstractmethod
    async def create(self, creative: Creative) -> Creative:
        ...

    @abstractmethod
    async def update(self, creative: Creative) -> Creative:
        ...

    @abstractmethod
    async def soft_delete(self, creative_id: str) -> None:
        ...