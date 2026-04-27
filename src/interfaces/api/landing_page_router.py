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


@router.post("/{lp_id}/duplicate", response_model=LandingPageResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_landing_page(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Duplicate an entire landing page with all its sections."""
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from domain.entities.landing_page import LandingPage as LP, LandingPageSection
    from domain.entities.base import LandingPageStatus

    repo = LandingPageSQLAlchemyRepository(session)
    src = await repo.get_by_id(lp_id)
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    copy = LP(
        organization_id=src.organization_id,
        brand_id=src.brand_id,
        name=f"{src.name} (copia)",
        campaign=src.campaign,
        status=LandingPageStatus.DRAFT,
        template=src.template,
        seo_title=getattr(src, "seo_title", None),
        seo_description=getattr(src, "seo_description", None),
        og_image=getattr(src, "og_image", None),
        analytics_config=getattr(src, "analytics_config", None),
    )
    session.add(copy)
    await session.flush()

    for s in sorted(src.sections, key=lambda x: x.order):
        session.add(LandingPageSection(
            landing_page_id=copy.id,
            section_type=s.section_type,
            title=s.title, body=s.body,
            cta_text=s.cta_text, cta_url=s.cta_url,
            image_url=s.image_url, images=s.images,
            order=s.order, is_visible=s.is_visible, content=s.content,
            ab_group=getattr(s, "ab_group", None),
        ))

    await session.commit()
    copy = await repo.get_by_id(copy.id)
    return LandingPageResponse.model_validate(copy)


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

    # ── Resource limit check ──
    from app.use_cases.resource_limits import check_resource_limit, ResourceLimitExceededError
    try:
        await check_resource_limit(session, org_id, "landing_pages")
    except ResourceLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

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


@router.post("/sections/{section_id}/regenerate", response_model=LandingSectionResponse)
async def regenerate_section(
    section_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a section's content using the AI landing page agent."""
    import json as _json
    import re as _re
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository
    from app.agents.agent_registry import get_agent

    repo = LandingPageSQLAlchemyRepository(session)
    section = await repo.get_section_by_id(section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    lp = await repo.get_by_id(section.landing_page_id)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    # ── Credit check & deduction (3 credits per section regeneration) ──
    from sqlalchemy import select as _rsel
    from domain.entities.organization import Organization
    from domain.entities.plan import Plan
    _REGEN_COST = 3
    _rorg_res = await session.execute(_rsel(Organization).where(Organization.id == lp.organization_id))
    _rorg = _rorg_res.scalar_one_or_none()
    if _rorg:
        _rplan_res = await session.execute(_rsel(Plan).where(Plan.id == _rorg.plan_id))
        _rplan = _rplan_res.scalar_one_or_none()
        if _rplan and _rorg.credits_used_this_month + _REGEN_COST > _rplan.max_credits_per_month:
            remaining = _rplan.max_credits_per_month - _rorg.credits_used_this_month
            raise HTTPException(status_code=402, detail=f"Créditos insuficientes: necesitas {_REGEN_COST}, te quedan {remaining}.")

    brand = None
    if lp.brand_id:
        brand_repo = BrandSQLAlchemyRepository(session)
        brand = await brand_repo.get_by_id(lp.brand_id)

    section_type = section.section_type.value if hasattr(section.section_type, "value") else str(section.section_type)
    brand_name = brand.name if brand else lp.name
    brand_desc = getattr(brand, "description", "") or ""
    campaign = getattr(lp, "campaign", "") or ""

    # Build page context: other sections so AI stays coherent with the rest of the page
    other_sections = [s for s in sorted(lp.sections, key=lambda x: x.order) if s.id != section_id]
    page_ctx = ""
    if other_sections:
        lines = []
        for s in other_sections[:12]:
            st = s.section_type.value if hasattr(s.section_type, "value") else str(s.section_type)
            snippet = (s.title or "")[:60] or (s.body or "")[:60]
            lines.append(f"  - {st}: {snippet}")
        page_ctx = "\nOther sections on this page (for context and consistency):\n" + "\n".join(lines) + "\n"

    prompt = (
        f'Regenerate the "{section_type}" section for this landing page.\n\n'
        f"Brand/Product: {brand_name}\n"
        + (f"Description: {brand_desc}\n" if brand_desc else "")
        + (f"Campaign: {campaign}\n" if campaign else "")
        + page_ctx
        + f'\nCurrent title: {section.title or "(none)"}\n'
        f'\nOutput ONLY a single valid JSON object. No explanations. No markdown text before or after. Just the JSON:\n'
        f'{{\n'
        f'  "title": "...",\n'
        f'  "body": "...",\n'
        f'  "cta_text": "...",\n'
        f'  "cta_url": "...",\n'
        f'  "content": {{...}}\n'
        f'}}\n'
        f'\nFollow the exact content schema for section type "{section_type}" from your system prompt. Keep brand voice consistent with other sections.'
    )

    agent = get_agent("landing_page")
    if not agent:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI agent unavailable")

    try:
        result = await agent.execute(prompt, temperature=0.75, max_tokens=4096)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent error: {e}")

    raw = result.get("content") or ""

    # Extract JSON — try code block first, then bare object
    json_data = None
    code_match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, _re.DOTALL)
    if code_match:
        try:
            json_data = _json.loads(code_match.group(1))
        except Exception:
            pass

    if not json_data:
        obj_match = _re.search(r"(\{[\s\S]*\})", raw)
        if obj_match:
            try:
                json_data = _json.loads(obj_match.group(1))
            except Exception:
                pass

    if not json_data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Agent returned unparseable response")

    if json_data.get("title"):
        section.title = str(json_data["title"])
    if json_data.get("body"):
        section.body = str(json_data["body"])
    if json_data.get("cta_text"):
        section.cta_text = str(json_data["cta_text"])
    if json_data.get("cta_url"):
        section.cta_url = str(json_data["cta_url"])
    if json_data.get("content") and isinstance(json_data["content"], dict):
        section.content = json_data["content"]

    if _rorg:
        _rorg.credits_used_this_month += _REGEN_COST

    await session.commit()
    await session.refresh(section)
    return LandingSectionResponse.model_validate(section)


@router.post("/sections/{section_id}/duplicate", response_model=LandingSectionResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_section(
    section_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Duplicate an existing section and append it right after the original."""
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from domain.entities.landing_page import LandingPageSection
    repo = LandingPageSQLAlchemyRepository(session)
    src = await repo.get_section_by_id(section_id)
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    lp = await repo.get_by_id(src.landing_page_id)
    max_order = max((s.order for s in lp.sections), default=0) if lp else src.order
    copy = LandingPageSection(
        landing_page_id=src.landing_page_id,
        section_type=src.section_type,
        title=src.title,
        body=src.body,
        cta_text=src.cta_text,
        cta_url=src.cta_url,
        image_url=src.image_url,
        images=src.images,
        order=max_order + 1,
        is_visible=src.is_visible,
        content=src.content,
    )
    copy = await repo.add_section(copy)
    await session.commit()
    return LandingSectionResponse.model_validate(copy)


@router.get("/{lp_id}/sections/{section_id}/render", response_class=HTMLResponse)
async def render_section_preview(
    lp_id: str,
    section_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Render a single section as a complete HTML document (for live preview)."""
    from app.use_cases.landing.html_render import LandingHTMLRender, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    renderer = LandingHTMLRender(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        html = await renderer.render_one_section(lp_id, section_id)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return HTMLResponse(content=html)


@router.post("/{lp_id}/sections/{section_id}/preview", response_class=HTMLResponse)
async def live_preview_section(
    lp_id: str,
    section_id: str,
    body: SectionPreviewRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Render a section with temporary (unsaved) data — for live WYSIWYG preview."""
    from app.use_cases.landing.html_render import LandingHTMLRender, LandingRenderError, render_section, html_shell, Theme
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp_id)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    brand = None
    if lp.brand_id:
        brand_repo = BrandSQLAlchemyRepository(session)
        brand = await brand_repo.get_by_id(lp.brand_id)

    c = brand.color_palette or {} if brand else {}
    ty = brand.typography or {} if brand else {}
    theme = Theme(
        primary=c.get("primary", "#6D28D9"),
        secondary=c.get("secondary", "#1E1B4B"),
        accent=c.get("accent", "#A78BFA"),
        background=c.get("background", "#ffffff"),
        text=c.get("text", "#111827"),
        heading_font=ty.get("heading_font", "Outfit"),
        body_font=ty.get("body_font", "DM Sans"),
    )

    # Build a temporary section object with the preview data
    class _TempSection:
        pass

    tmp = _TempSection()
    tmp.section_type = body.section_type
    tmp.title = body.title
    tmp.body = body.body
    tmp.cta_text = body.cta_text
    tmp.cta_url = body.cta_url
    tmp.content = body.content or {}
    tmp.image_url = body.image_url
    tmp.images = None
    tmp.id = section_id

    brand_name = brand.name if brand else lp.name
    template_id = getattr(lp, "template", None) or "modern"
    rendered = render_section(tmp, theme)
    html = html_shell(rendered, lp.name, brand_name, theme, template_id)
    return HTMLResponse(content=html)


@router.post("/{lp_id}/leads", status_code=status.HTTP_201_CREATED)
async def submit_lead(
    lp_id: str,
    body: SubmitLeadRequest,
    session: AsyncSession = Depends(get_session),
):
    """Public endpoint — capture a lead form submission (no auth required)."""
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from domain.entities.landing_page import LandingLead

    repo = LandingPageSQLAlchemyRepository(session)
    lp = await repo.get_by_id(lp_id)
    if not lp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")

    lead = LandingLead(
        landing_page_id=lp_id,
        section_id=body.section_id or None,
        data=body.data or {},
    )
    session.add(lead)
    await session.commit()
    return {"ok": True, "id": lead.id}


@router.get("/{lp_id}/render", response_class=HTMLResponse)
async def render_landing_page(
    lp_id: str,
    variant: str | None = Query(default=None, description="A/B variant filter: 'a' or 'b'"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Render the landing page as a complete HTML document. Use ?variant=a|b to filter A/B sections."""
    from app.use_cases.landing.html_render import LandingHTMLRender, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository

    renderer = LandingHTMLRender(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        html = await renderer.render(lp_id, ab_variant=variant)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return HTMLResponse(content=html)


@router.get("/{lp_id}/export/html")
async def export_html_file(
    lp_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Export the landing page as a standalone downloadable HTML file."""
    from app.use_cases.landing.html_render import LandingHTMLRender, LandingRenderError
    from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
    from infra.adapters.brand_sqlalchemy import BrandSQLAlchemyRepository
    from fastapi.responses import Response

    renderer = LandingHTMLRender(
        lp_repo=LandingPageSQLAlchemyRepository(session),
        brand_repo=BrandSQLAlchemyRepository(session),
    )
    try:
        html = await renderer.render(lp_id)
    except LandingRenderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="landing-{lp_id}.html"'},
    )


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
