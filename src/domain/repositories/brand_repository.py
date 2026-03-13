"""
Contrato de acceso a datos para Brand.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.brand import Brand


class BrandRepository(ABC):

    @abstractmethod
    async def get_by_id(self, brand_id: str) -> Optional[Brand]:
        ...

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> List[Brand]:
        ...

    @abstractmethod
    async def create(self, brand: Brand) -> Brand:
        ...

    @abstractmethod
    async def update(self, brand: Brand) -> Brand:
        ...

    @abstractmethod
    async def soft_delete(self, brand_id: str) -> None:
        ...