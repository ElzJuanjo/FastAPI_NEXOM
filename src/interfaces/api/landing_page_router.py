from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from infra.config.database import get_session
from app.dto.landing_page_dto import *
from app.use_cases.landing.crud import *
from interfaces.dependencies.landing_page_dependencies import *
from interfaces.dependencies.auth_dependencies import get_current_user_id

from interfaces.dependencies.org_membership import verify_brand_access

router = APIRouter(prefix="/landing-pages", tags=["Landing Pages"])


@router.post("", response_model=LandingPageResponse, status_code=status.HTTP_201_CREATED)
async def create_landing_page(
    body: CreateLandingPageRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: LandingPageCreate = Depends(get_lp_create),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select as sa_select
    from domain.entities.organization import OrganizationMember
    stmt = sa_select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.is_owner == True,
        OrganizationMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    org_id = result.scalar_one_or_none()
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization found")

    sections_data = [s.model_dump() for s in body.sections] if body.sections else None
    lp = await use_case.execute(org_id=org_id, name=body.name, brand_id=body.brand_id, campaign=body.campaign, sections_data=sections_data)
    await session.commit()

    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp.id)
    return LandingPageResponse.model_validate(lp)


@router.get("", response_model=LandingPageListResponse)
async def list_landing_pages(
    brand_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    from interfaces.dependencies.org_membership import get_current_org_id
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository

    # Get org_id from the dependency manually
    from sqlalchemy import select as sa_select
    from domain.entities.organization import OrganizationMember
    stmt = sa_select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.is_owner == True,
        OrganizationMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    org_id = result.scalar_one_or_none()
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization found")

    repo = LandingPageSQLAlchemyRepository(session)
    lps = await repo.list_by_organization(org_id, brand_id=brand_id if brand_id else None)
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


@router.post("/{lp_id}/sections", response_model=LandingSectionResponse, status_code=status.HTTP_201_CREATED)
async def add_section(
    lp_id: str,
    body: CreateLandingSectionRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Add a new section to an existing landing page."""
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from domain.entities.landing_page import LandingPageSection
    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp_id)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    section = LandingPageSection(
        landing_page_id=lp_id,
        section_type=body.section_type,
        title=body.title,
        body=body.body,
        cta_text=body.cta_text,
        cta_url=body.cta_url,
        order=body.order,
        is_visible=body.is_visible,
        content=body.content,
    )
    section = await repo.add_section(section)
    await session.commit()
    return LandingSectionResponse.model_validate(section)


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


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    repo = LandingPageSQLAlchemyRepository(session)
    section = await repo.get_section_by_id(section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    await session.delete(section)
    await session.commit()


@router.get("/{lp_id}/render", response_class=HTMLResponse)
async def render_landing_page(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Render the landing page as a complete HTML document."""
    from app.use_cases.landing.html_render import LandingHTMLRender, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    renderer = LandingHTMLRender(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        html = await renderer.render(lp_id)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return HTMLResponse(content=html)


@router.get("/{lp_id}/export/shopify", response_class=HTMLResponse)
async def export_shopify(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Export the landing page as Shopify Liquid template."""
    from app.use_cases.landing.export import LandingExporter, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    exporter = LandingExporter(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        content = await exporter.export_shopify(lp_id)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return HTMLResponse(content=content, media_type="text/plain")


@router.get("/{lp_id}/export/wordpress", response_class=HTMLResponse)
async def export_wordpress(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Export the landing page as WordPress-compatible HTML block."""
    from app.use_cases.landing.export import LandingExporter, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    exporter = LandingExporter(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        content = await exporter.export_wordpress(lp_id)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return HTMLResponse(content=content, media_type="text/plain")


@router.post("/{lp_id}/reorder", response_model=LandingPageResponse)
async def reorder_sections(
    lp_id: str,
    body: ReorderSectionsRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Reorder sections of a landing page."""
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp_id)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    section_map = {s.id: s for s in lp.sections}

    # Temporarily set all orders to high values to avoid unique constraint conflicts
    for i, s in enumerate(lp.sections):
        s.order = 9000 + i
    await session.flush()

    # Apply new order
    for new_order, section_id in enumerate(body.section_ids, start=1):
        if section_id in section_map:
            section_map[section_id].order = new_order
    await session.flush()
    await session.commit()

    lp = await repo.get_by_id(lp_id)
    return LandingPageResponse.model_validate(lp)