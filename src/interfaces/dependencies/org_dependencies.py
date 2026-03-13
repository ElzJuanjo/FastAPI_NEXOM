"""
Dependencias de inyección para Organizations y Plans.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.plan_sqlalchemy import PlanSQLAlchemyRepository
from infra.adapters.organization_sqlalchemy import OrganizationSQLAlchemyRepository
from domain.repositories.plan_repository import PlanRepository
from domain.repositories.organization_repository import OrganizationRepository
from app.use_cases.org_create import OrgCreate
from app.use_cases.org_list import OrgList
from app.use_cases.plan_seed import PlanSeed


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------

def get_plan_repository(session: AsyncSession = Depends(get_session)) -> PlanRepository:
    return PlanSQLAlchemyRepository(session)


def get_org_repository(session: AsyncSession = Depends(get_session)) -> OrganizationRepository:
    return OrganizationSQLAlchemyRepository(session)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------

def get_org_create(
    org_repo: OrganizationRepository = Depends(get_org_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository),
) -> OrgCreate:
    return OrgCreate(org_repo, plan_repo)


def get_org_list(org_repo: OrganizationRepository = Depends(get_org_repository)) -> OrgList:
    return OrgList(org_repo)


def get_plan_seed(plan_repo: PlanRepository = Depends(get_plan_repository)) -> PlanSeed:
    return PlanSeed(plan_repo)