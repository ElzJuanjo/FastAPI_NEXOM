"""
Endpoints CRUD de Product, scoped por organización del usuario.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.product_dto import (
    CreateProductRequest, UpdateProductRequest,
    ProductResponse, ProductListResponse,
)
from app.use_cases.product_crud import ProductCreate, ProductList, ProductUpdate, ProductDelete, ProductNotFoundError
from interfaces.dependencies.product_dependencies import (
    get_product_create, get_product_list, get_product_update, get_product_delete,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: CreateProductRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: ProductCreate = Depends(get_product_create),
    session: AsyncSession = Depends(get_session),
):
    product = await use_case.execute(
        org_id=org_id,
        **body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return ProductResponse.model_validate(product)


@router.get("", response_model=ProductListResponse)
async def list_products(
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: ProductList = Depends(get_product_list),
):
    products = await use_case.execute(org_id)
    return ProductListResponse(products=[ProductResponse.model_validate(p) for p in products])


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    body: UpdateProductRequest,
    user_id: str = Depends(get_current_user_id),
    use_case: ProductUpdate = Depends(get_product_update),
    session: AsyncSession = Depends(get_session),
):
    try:
        product = await use_case.execute(
            product_id=product_id,
            **body.model_dump(exclude_unset=True),
        )
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await session.commit()
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    import logging
    from domain.entities.product import Product
    from domain.entities.creative import Creative
    from sqlalchemy import select
    from infra.tools.s3_client import delete_s3_object

    logger = logging.getLogger(__name__)

    # Verificar que existe
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    # Eliminar creativos asociados (S3 + BD)
    creative_stmt = select(Creative).where(Creative.product_id == product_id)
    creative_result = await session.execute(creative_stmt)
    creatives = list(creative_result.scalars().all())

    for creative in creatives:
        s3_key = creative.s3_key
        if not s3_key and creative.file_url and ".amazonaws.com/" in creative.file_url:
            try:
                s3_key = creative.file_url.split(".amazonaws.com/", 1)[1]
            except (IndexError, AttributeError):
                pass
        if s3_key:
            await delete_s3_object(s3_key)
        await session.delete(creative)

    logger.info(f"Deleted {len(creatives)} creatives for product {product_id}")

    # Hard delete producto
    await session.delete(product)
    await session.commit()
    logger.info(f"Product {product_id} hard deleted")
