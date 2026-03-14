from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from infra.config.database import get_session
from app.dto.landing_page_dto import *
from app.use_cases.landing_page_crud import *
from interfaces.dependencies.landing_page_dependencies import *
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/landing-pages", tags=["Landing Pages"])


@router.post("", response_model=LandingPageResponse, status_code=status.HTTP_201_CREATED)
async def create_landing_page(
    body: CreateLandingPageRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: LandingPageCreate = Depends(get_lp_create),
    session: AsyncSession = Depends(get_session),
):
    sections_data = [s.model_dump() for s in body.sections] if body.sections else None
    lp = await use_case.execute(brand_id=body.brand_id, name=body.name, campaign=body.campaign, sections_data=sections_data)
    await session.commit()

    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp.id)
    return LandingPageResponse.model_validate(lp)


@router.get("", response_model=LandingPageListResponse)
async def list_landing_pages(
    brand_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    use_case: LandingPageList = Depends(get_lp_list),
):
    lps = await use_case.execute(brand_id)
    return LandingPageListResponse(landing_pages=[LandingPageResponse.model_validate(lp) for lp in lps])


@router.patch("/{lp_id}", response_model=LandingPageResponse)
async def update_landing_page(
    lp_id: str,
    body: UpdateLandingPageRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: LandingPageUpdate = Depends(get_lp_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        lp = await use_case.execute(lp_id, **body.model_dump(exclude_unset=True))
    except LandingPageNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return LandingPageResponse.model_validate(lp)


@router.delete("/{lp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_landing_page(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: LandingPageDelete = Depends(get_lp_delete),
    session: AsyncSession = Depends(get_session),
):
    try:
        await use_case.execute(lp_id)
    except LandingPageNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()


@router.patch("/sections/{section_id}", response_model=LandingSectionResponse)
async def update_section(
    section_id: str,
    body: UpdateLandingSectionRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: LandingSectionUpdate = Depends(get_section_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        section = await use_case.execute(section_id, **body.model_dump(exclude_unset=True))
    except LandingSectionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return LandingSectionResponse.model_validate(section)