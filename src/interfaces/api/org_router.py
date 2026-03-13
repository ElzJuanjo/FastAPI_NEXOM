"""
Endpoints de Organizations y Plans.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.organization_dto import (
    CreateOrganizationRequest, OrganizationResponse,
    OrganizationListResponse, PlanResponse,
)
from app.use_cases.org_create import OrgCreate, SlugAlreadyExistsError, PlanNotFoundError
from app.use_cases.org_list import OrgList
from app.use_cases.plan_seed import PlanSeed
from interfaces.dependencies.org_dependencies import (
    get_org_create, get_org_list, get_plan_seed, get_plan_repository,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from domain.repositories.plan_repository import PlanRepository

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: CreateOrganizationRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: OrgCreate = Depends(get_org_create),
    session: AsyncSession = Depends(get_session),
):
    try:
        org = await use_case.execute(
            name=body.name,
            slug=body.slug,
            timezone_str=body.timezone,
            owner_user_id=user_id,
        )
    except SlugAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PlanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    await session.commit()

    # Recargar con relaciones para el response
    from interfaces.dependencies.org_dependencies import get_org_repository
    org_repo = get_org_repository.__wrapped__(session) if hasattr(get_org_repository, '__wrapped__') else OrganizationSQLAlchemyRepository(session)
    from infra.adapters.organization_sqlalchemy import OrganizationSQLAlchemyRepository
    org_repo = OrganizationSQLAlchemyRepository(session)
    org = await org_repo.get_by_id(org.id)

    return OrganizationResponse.model_validate(org)


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    user_id: str = Depends(get_current_user_id),
    use_case: OrgList = Depends(get_org_list),
):
    orgs = await use_case.execute(user_id)
    return OrganizationListResponse(
        organizations=[OrganizationResponse.model_validate(o) for o in orgs]
    )


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

plans_router = APIRouter(prefix="/plans", tags=["Plans"])


@plans_router.get("", response_model=list[PlanResponse])
async def list_plans(plan_repo: PlanRepository = Depends(get_plan_repository)):
    plans = await plan_repo.get_all()
    return [PlanResponse.model_validate(p) for p in plans]


@plans_router.post("/seed", response_model=list[PlanResponse], status_code=status.HTTP_201_CREATED)
async def seed_plans(
    use_case: PlanSeed = Depends(get_plan_seed),
    session: AsyncSession = Depends(get_session),
):
    created = await use_case.execute()
    await session.commit()
    return [PlanResponse.model_validate(p) for p in created]