"""
Casos de uso: Actualizar organización y cambiar plan.
Solo el owner puede realizar estas acciones.
"""

from domain.entities.organization import Organization
from domain.entities.base import PlanType
from domain.repositories.organization_repository import OrganizationRepository
from domain.repositories.plan_repository import PlanRepository


class OrgNotFoundError(Exception):
    pass


class SlugAlreadyExistsError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass


class SamePlanError(Exception):
    pass


class OrgUpdate:

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, org_id: str, **kwargs) -> Organization:
        org = await self._org_repo.get_by_id(org_id)
        if not org:
            raise OrgNotFoundError(f"Organización {org_id} no encontrada")

        # Si se cambia el slug, verificar unicidad
        new_slug = kwargs.get("slug")
        if new_slug and new_slug != org.slug:
            existing = await self._org_repo.get_by_slug(new_slug)
            if existing:
                raise SlugAlreadyExistsError(f"El slug '{new_slug}' ya está en uso")

        for key, value in kwargs.items():
            if value is not None and hasattr(org, key):
                setattr(org, key, value)

        return org


class OrgChangePlan:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        plan_repo: PlanRepository,
    ) -> None:
        self._org_repo = org_repo
        self._plan_repo = plan_repo

    async def execute(self, org_id: str, new_plan_type: str) -> Organization:
        """
        Cambia el plan de la organización.
        En el futuro, esto se integrará con Stripe para cobro.
        Por ahora solo actualiza el plan_id.
        """
        org = await self._org_repo.get_by_id(org_id)
        if not org:
            raise OrgNotFoundError(f"Organización {org_id} no encontrada")

        # Validar que el plan existe
        new_plan = await self._plan_repo.get_by_type(new_plan_type)
        if not new_plan:
            raise PlanNotFoundError(f"Plan '{new_plan_type}' no encontrado")

        # Verificar que no sea el mismo plan
        if org.plan_id == new_plan.id:
            raise SamePlanError("Ya tienes este plan activo")

        org.plan_id = new_plan.id

        return org
