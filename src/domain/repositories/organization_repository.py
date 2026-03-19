"""
Contrato de acceso a datos para Organization y OrganizationMember.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.organization import Organization, OrganizationMember


class OrganizationRepository(ABC):

    @abstractmethod
    async def get_by_id(self, org_id: str) -> Optional[Organization]:
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        ...

    @abstractmethod
    async def get_by_owner(self, user_id: str) -> Optional[Organization]:
        """Retorna la organización donde el usuario es owner (máx 1)."""
        ...

    @abstractmethod
    async def create(self, organization: Organization) -> Organization:
        ...

    @abstractmethod
    async def get_member(self, org_id: str, user_id: str) -> Optional[OrganizationMember]:
        ...

    @abstractmethod
    async def add_member(self, member: OrganizationMember) -> OrganizationMember:
        ...

    @abstractmethod
    async def list_by_user(self, user_id: str) -> List[Organization]:
        ...
