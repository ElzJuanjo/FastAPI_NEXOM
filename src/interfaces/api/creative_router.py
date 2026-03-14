from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from infra.config.database import get_session
from app.dto.creative_dto import (
    CreateCreativeRequest, UpdateCreativeRequest,
    CreativeResponse, CreativeListResponse,
)
from app.use_cases.creative_crud import CreativeCreate, CreativeList, CreativeUpdate, CreativeDelete, CreativeNotFoundError
from interfaces.dependencies.creative_dependencies import (
    get_creative_create, get_creative_list, get_creative_update, get_creative_delete,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id

router = APIRouter(prefix="/creatives", tags=["Creatives"])


@router.post("", response_model=CreativeResponse, status_code=status.HTTP_201_CREATED)
async def create_creative(
    body: CreateCreativeRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: CreativeCreate = Depends(get_creative_create),
    session: AsyncSession = Depends(get_session),
):
    creative = await use_case.execute(**body.model_dump())
    await session.commit()
    return CreativeResponse.model_validate(creative)


@router.get("", response_model=CreativeListResponse)
async def list_creatives(
    product_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    use_case: CreativeList = Depends(get_creative_list),
):
    creatives = await use_case.execute(product_id)
    return CreativeListResponse(creatives=[CreativeResponse.model_validate(c) for c in creatives])


@router.patch("/{creative_id}", response_model=CreativeResponse)
async def update_creative(
    creative_id: str,
    body: UpdateCreativeRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: CreativeUpdate = Depends(get_creative_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        creative = await use_case.execute(creative_id, **body.model_dump(exclude_unset=True))
    except CreativeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return CreativeResponse.model_validate(creative)


@router.delete("/{creative_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creative(
    creative_id: str,
    user_id: str = Depends(get_current_user_id),
    use_case: CreativeDelete = Depends(get_creative_delete),
    session: AsyncSession = Depends(get_session),
):
    try:
        await use_case.execute(creative_id)
    except CreativeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()