"""
Caso de uso: Listar organizaciones a las que pertenece un usuario.
"""

from typing import List

from domain.entities.organization import Organization
from domain.repositories.organization_repository import OrganizationRepository


class OrgList:

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, user_id: str) -> List[Organization]:
        return await self._org_repo.list_by_user(user_id)