"""
Contrato de acceso a datos para Product.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.product import Product


class ProductRepository(ABC):

    @abstractmethod
    async def get_by_id(self, product_id: str) -> Optional[Product]:
        ...

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> List[Product]:
        ...

    @abstractmethod
    async def list_by_brand(self, brand_id: str) -> List[Product]:
        ...

    @abstractmethod
    async def create(self, product: Product) -> Product:
        ...

    @abstractmethod
    async def update(self, product: Product) -> Product:
        ...

    @abstractmethod
    async def soft_delete(self, product_id: str) -> None:
        ...