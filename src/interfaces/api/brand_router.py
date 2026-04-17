"""
Endpoints CRUD de Brand, scoped por organización del usuario.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.brand_dto import (
    CreateBrandRequest, UpdateBrandRequest,
    BrandResponse, BrandListResponse,
)
from app.use_cases.brand.crud import BrandCreate, BrandList, BrandUpdate, BrandDelete, BrandNotFoundError
from interfaces.dependencies.brand_dependencies import (
    get_brand_create, get_brand_list, get_brand_update, get_brand_delete,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

router = APIRouter(prefix="/brands", tags=["Brands"])


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    body: CreateBrandRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: BrandCreate = Depends(get_brand_create),
    session: AsyncSession = Depends(get_session),
):
    # ── Resource limit check ──
    from app.use_cases.resource_limits import check_resource_limit, ResourceLimitExceededError
    try:
        await check_resource_limit(session, org_id, "brands")
    except ResourceLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    brand = await use_case.execute(
        org_id=org_id,
        name=body.name,
        tagline=body.tagline,
        color_palette=body.color_palette,
        typography=body.typography,
        tones=body.tones,
        key_messages=body.key_messages,
    )
    await session.commit()
    return BrandResponse.model_validate(brand)


@router.get("", response_model=BrandListResponse)
async def list_brands(
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: BrandList = Depends(get_brand_list),
):
    brands = await use_case.execute(org_id)
    return BrandListResponse(brands=[BrandResponse.model_validate(b) for b in brands])


@router.get("/templates", response_model=list)
async def list_brand_templates():
    """Lista templates de identidad de marca por nicho."""
    from app.use_cases.brand.templates import get_brand_templates
    return get_brand_templates()


@router.post("/from-template/{template_id}", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand_from_template(
    template_id: str,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: BrandCreate = Depends(get_brand_create),
    session: AsyncSession = Depends(get_session),
):
    """Crea una marca a partir de un template predefinido."""
    # ── Resource limit check ──
    from app.use_cases.resource_limits import check_resource_limit, ResourceLimitExceededError
    try:
        await check_resource_limit(session, org_id, "brands")
    except ResourceLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    from app.use_cases.brand.templates import get_template_by_id
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")

    brand = await use_case.execute(
        org_id=org_id,
        name=template["name"],
        color_palette=template["color_palette"],
        typography=template["typography"],
        tones=template["tones"],
        key_messages=template["key_messages"],
    )
    await session.commit()
    return BrandResponse.model_validate(brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: BrandList = Depends(get_brand_list),
    session: AsyncSession = Depends(get_session),
):
    """Obtiene una marca por ID."""
    from domain.entities.brand import Brand
    from sqlalchemy import select as sa_select
    stmt = sa_select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None))
    result = await session.execute(stmt)
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand no encontrada")
    return BrandResponse.model_validate(brand)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: str,
    body: UpdateBrandRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: BrandUpdate = Depends(get_brand_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        brand = await use_case.execute(
            brand_id=brand_id,
            **body.model_dump(exclude_unset=True),
        )
    except BrandNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return BrandResponse.model_validate(brand)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: BrandDelete = Depends(get_brand_delete),
    session: AsyncSession = Depends(get_session),
):
    try:
        await use_case.execute(brand_id)
    except BrandNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()


@router.get("/{brand_id}/export-pdf")
async def export_brand_pdf(
    brand_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Exporta brand guidelines como PDF."""
    from app.use_cases.brand.export_pdf import export_brand_guidelines_pdf
    from fastapi.responses import Response

    # Cargar brand
    from domain.entities.brand import Brand
    from sqlalchemy import select as sa_select
    stmt = sa_select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None))
    result = await session.execute(stmt)
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand no encontrada")

    pdf_bytes = await export_brand_guidelines_pdf(brand)
    filename = f"brand-guidelines-{brand.name.lower().replace(' ', '-')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
