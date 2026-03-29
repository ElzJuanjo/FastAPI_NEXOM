from abc import ABC, abstractmethod
from typing import Optional, List
from domain.entities.landing_page import LandingPage, LandingPageSection


class LandingPageRepository(ABC):

    @abstractmethod
    async def get_by_id(self, lp_id: str) -> Optional[LandingPage]:
        ...

    @abstractmethod
    async def list_by_brand(self, brand_id: str) -> List[LandingPage]:
        ...

    @abstractmethod
    async def list_by_organization(self, org_id: str, brand_id: str | None = None) -> List[LandingPage]:
        ...

    @abstractmethod
    async def create(self, lp: LandingPage) -> LandingPage:
        ...

    @abstractmethod
    async def update(self, lp: LandingPage) -> LandingPage:
        ...

    @abstractmethod
    async def soft_delete(self, lp_id: str) -> None:
        ...

    @abstractmethod
    async def add_section(self, section: LandingPageSection) -> LandingPageSection:
        ...

    @abstractmethod
    async def update_section(self, section: LandingPageSection) -> LandingPageSection:
        ...

    @abstractmethod
    async def get_section_by_id(self, section_id: str) -> Optional[LandingPageSection]:
        ...