"""
Endpoints CRUD de Product, scoped por organización del usuario.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.product_dto import (
    CreateProductRequest, UpdateProductRequest,
    ProductResponse, ProductListResponse,
    ImportDropiRequest, ImportDropiResponse,
)
from app.use_cases.product.crud import ProductCreate, ProductList, ProductUpdate, ProductDelete, ProductNotFoundError
from interfaces.dependencies.product_dependencies import (
    get_product_create, get_product_list, get_product_update, get_product_delete,
)
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id

logger = logging.getLogger(__name__)

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


@router.post("/import-dropi", response_model=ImportDropiResponse)
async def import_from_dropi(
    body: ImportDropiRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: ProductCreate = Depends(get_product_create),
    session: AsyncSession = Depends(get_session),
):
    """
    Importa un producto desde Dropi por su ID.
    """
    import re
    from infra.tools.dropi_client import dropi_client, DropisError

    dropi_id = body.dropi_product_id.strip()

    try:
        dropi_product = await dropi_client.get_product(int(dropi_id))
    except DropisError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al conectar con Dropi: {e.detail}",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID de producto Dropi debe ser numérico",
        )

    if not dropi_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto Dropi #{dropi_id} no encontrado",
        )

    # Map fields
    name = dropi_product.get("name", f"Dropi #{dropi_id}")[:255]
    price_cop = dropi_product.get("suggested_price") or dropi_product.get("price", 0)
    price_usd = round(float(price_cop) / 4200, 2) if price_cop and float(price_cop) > 0 else None
    image_url = dropi_product.get("image_url", "") or None
    stock = dropi_product.get("stock", 0)
    variations = dropi_product.get("variations", [])
    category = dropi_product.get("category", "")
    supplier = dropi_product.get("supplier", "")

    # Use Dropi's own product description, fallback to category
    raw_desc = dropi_product.get("description", "")
    if raw_desc:
        description = re.sub(r'<[^>]+>', '', raw_desc).strip()[:500]
    else:
        description = category or "Importado desde Dropi"

    # Structured extra_data
    extra_data = {
        "dropi_import": True,
        "source": "dropi",
        "source_platform": "dropi",
        "source_url": f"https://dropi.co/catalog/product/{dropi_id}",
        "price_cop": float(dropi_product.get("price", 0)),
        "suggested_price_cop": float(price_cop),
        "stock": stock,
        "category": category,
        "supplier": supplier,
        "sku": dropi_product.get("sku", ""),
        "type": dropi_product.get("type", "SIMPLE"),
        "variations": variations,
        "variations_count": len(variations),
    }

    product = await use_case.execute(
        org_id=org_id,
        name=name,
        description=description,
        price_usd=price_usd,
        image_url=image_url,
        dropi_product_id=dropi_id,
        extra_data=extra_data,
    )
    await session.commit()

    return ImportDropiResponse(
        product=ProductResponse.model_validate(product),
        dropi_name=name,
        dropi_stock=stock,
        variations_count=len(variations),
    )


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
    from domain.entities.product import Product
    from domain.entities.creative import Creative
    from sqlalchemy import select
    from infra.tools.s3_client import delete_s3_object

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
    