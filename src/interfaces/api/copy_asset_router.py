"""
Endpoints CRUD de CopyAsset, scoped por organización del usuario.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.copy_asset_dto import (
    CreateCopyAssetRequest, UpdateCopyAssetRequest,
    CopyAssetResponse, CopyAssetListResponse,
)
from app.use_cases.copy_asset_crud import (
    CopyAssetCreate, CopyAssetList, CopyAssetUpdate, CopyAssetDelete,
    CopyAssetNotFoundError,
)
from interfaces.dependencies.copy_asset_dependencies import (
    get_copy_asset_create, get_copy_asset_list,
    get_copy_asset_update, get_copy_asset_delete,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

router = APIRouter(prefix="/copy-assets", tags=["CopyAssets"])


@router.post("", response_model=CopyAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_copy_asset(
    body: CreateCopyAssetRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: CopyAssetCreate = Depends(get_copy_asset_create),
    session: AsyncSession = Depends(get_session),
):
    asset = await use_case.execute(
        org_id=org_id,
        **body.model_dump(exclude_unset=True),
    )
    await session.commit()
    await session.refresh(asset)
    return CopyAssetResponse.model_validate(asset)


@router.get("", response_model=CopyAssetListResponse)
async def list_copy_assets(
    copy_type: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    asset_status: str | None = Query(default=None, alias="status"),
    brand_id: str | None = Query(default=None),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: CopyAssetList = Depends(get_copy_asset_list),
):
    assets = await use_case.execute(org_id, copy_type, platform, asset_status, brand_id)
    return CopyAssetListResponse(assets=[CopyAssetResponse.model_validate(a) for a in assets])


@router.get("/{asset_id}", response_model=CopyAssetResponse)
async def get_copy_asset(
    asset_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    from domain.entities.copy_asset import CopyAsset
    from sqlalchemy import select
    stmt = select(CopyAsset).where(CopyAsset.id == asset_id)
    result = await session.execute(stmt)
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="CopyAsset no encontrado")
    return CopyAssetResponse.model_validate(asset)


@router.patch("/{asset_id}", response_model=CopyAssetResponse)
async def update_copy_asset(
    asset_id: str,
    body: UpdateCopyAssetRequest,
    org_id: str = Depends(get_current_org_id), 
    user_id: str = Depends(get_current_user_id),
    use_case: CopyAssetUpdate = Depends(get_copy_asset_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        asset = await use_case.execute(
            asset_id=asset_id,
            **body.model_dump(exclude_unset=True),
        )
    except CopyAssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await session.commit()
    await session.refresh(asset)
    return CopyAssetResponse.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_copy_asset(
    asset_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: CopyAssetDelete = Depends(get_copy_asset_delete),
    session: AsyncSession = Depends(get_session),
):
    try:
        await use_case.execute(asset_id)
    except CopyAssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await session.commit()