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
from app.use_cases.brand_crud import BrandCreate, BrandList, BrandUpdate, BrandDelete, BrandNotFoundError
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
