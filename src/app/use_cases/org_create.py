"""
Caso de uso: Crear organización.
Asigna plan FREE por defecto y agrega al usuario como owner.
Restricción: un usuario solo puede ser owner de UNA organización.
Idempotente — si el slug ya existe, lanza error controlado.
"""

from datetime import datetime, timezone

from domain.entities.organization import Organization, OrganizationMember
from domain.entities.base import UserRole, PlanType
from domain.repositories.organization_repository import OrganizationRepository
from domain.repositories.plan_repository import PlanRepository


class SlugAlreadyExistsError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass


class UserAlreadyHasOrganizationError(Exception):
    pass


class OrgCreate:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        plan_repo: PlanRepository,
    ) -> None:
        self._org_repo = org_repo
        self._plan_repo = plan_repo

    async def execute(self, name: str, slug: str, timezone_str: str, owner_user_id: str) -> Organization:
        # Restricción 1:1 — verificar que el usuario no sea owner de otra org
        existing_org = await self._org_repo.get_by_owner(owner_user_id)
        if existing_org:
            raise UserAlreadyHasOrganizationError(
                "Ya tienes una organización. Solo puedes tener una organización como propietario."
            )

        # Idempotencia: verificar slug único
        existing = await self._org_repo.get_by_slug(slug)
        if existing:
            raise SlugAlreadyExistsError(f"El slug '{slug}' ya está en uso")

        # Obtener plan FREE por defecto
        free_plan = await self._plan_repo.get_by_type(PlanType.FREE)
        if not free_plan:
            raise PlanNotFoundError("No existe el plan FREE. Ejecuta el seed de planes.")

        # Crear organización
        org = Organization(
            name=name,
            slug=slug,
            timezone=timezone_str,
            plan_id=free_plan.id,
        )
        org = await self._org_repo.create(org)

        # Agregar al creador como owner + admin
        member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_user_id,
            role=UserRole.ADMIN,
            is_owner=True,
            joined_at=datetime.now(timezone.utc),
        )
        await self._org_repo.add_member(member)

        return org
