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

from interfaces.dependencies.org_membership import get_current_org_id

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


@router.post("/from-url", response_model=CreativeResponse, status_code=status.HTTP_201_CREATED)
async def create_creative_from_url(
    body: dict,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Crea un creativo directamente desde una URL de S3 (sin re-subir)."""
    from domain.entities.creative import Creative
    from domain.entities.base import AssetStatus, AgentType

    file_url = body.get("file_url")
    if not file_url:
        raise HTTPException(status_code=400, detail="file_url es requerido")

    # Validar que no exista ya
    from sqlalchemy import select
    existing_stmt = select(Creative).where(
        Creative.file_url == file_url,
        Creative.organization_id == org_id,
        Creative.deleted_at.is_(None),
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta imagen ya está en creativos")

    # Extraer s3_key de la URL
    s3_key = None
    if ".amazonaws.com/" in file_url:
        try:
            s3_key = file_url.split(".amazonaws.com/", 1)[1]
        except (IndexError, AttributeError):
            pass

    creative = Creative(
        organization_id=org_id,
        agent_type=AgentType.IMAGE_GEN,
        status=AssetStatus.APPROVED,
        file_url=file_url,
        s3_key=s3_key,
        generation_prompt=body.get("generation_prompt"),
    )
    session.add(creative)
    await session.commit()
    await session.refresh(creative)

    return CreativeResponse.model_validate(creative)


@router.get("", response_model=CreativeListResponse)
async def list_creatives(
    product_id: str | None = Query(default=None),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Lista creativos de la organización, opcionalmente filtrados por producto."""
    from domain.entities.creative import Creative
    from sqlalchemy import select

    stmt = (
        select(Creative)
        .where(Creative.organization_id == org_id)
        .where(Creative.deleted_at.is_(None))
    )
    if product_id:
        stmt = stmt.where(Creative.product_id == product_id)

    stmt = stmt.order_by(Creative.created_at.desc())
    result = await session.execute(stmt)
    creatives = list(result.scalars().all())
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
    session: AsyncSession = Depends(get_session),
):
    from domain.entities.creative import Creative
    from sqlalchemy import select, delete as sql_delete
    from infra.tools.s3_client import delete_s3_object

    stmt = select(Creative).where(Creative.id == creative_id)
    result = await session.execute(stmt)
    creative = result.scalar_one_or_none()

    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative no encontrado")

    # Eliminar de S3
    if creative.s3_key:
        await delete_s3_object(creative.s3_key)
    elif creative.file_url and "s3.amazonaws.com" in (creative.file_url or ""):
        try:
            key = creative.file_url.split(".amazonaws.com/", 1)[1]
            await delete_s3_object(key)
        except Exception:
            pass

    # Hard delete de BD
    await session.delete(creative)
    await session.commit()
    
    
@router.get("/unassigned")
async def list_unassigned_creatives(
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Lista creativos sin producto asignado de esta organización."""
    from domain.entities.creative import Creative
    from sqlalchemy import select

    stmt = (
        select(Creative)
        .where(Creative.organization_id == org_id)
        .where(Creative.product_id.is_(None))
        .where(Creative.deleted_at.is_(None))
        .order_by(Creative.created_at.desc())
    )
    result = await session.execute(stmt)
    creatives = list(result.scalars().all())
    return CreativeListResponse(creatives=[CreativeResponse.model_validate(c) for c in creatives])

@router.patch("/{creative_id}/assign", response_model=CreativeResponse)
async def assign_product(
    creative_id: str,
    body: dict,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Asigna o desasigna un producto a un creativo."""
    from domain.entities.creative import Creative
    from sqlalchemy import select

    stmt = select(Creative).where(Creative.id == creative_id, Creative.deleted_at.is_(None))
    result = await session.execute(stmt)
    creative = result.scalar_one_or_none()

    if not creative:
        raise HTTPException(status_code=404, detail="Creative no encontrado")

    # Permitir null para desasignar
    product_id = body.get("product_id")  # puede ser string o None
    creative.product_id = product_id

    await session.commit()
    await session.refresh(creative)
    return CreativeResponse.model_validate(creative)