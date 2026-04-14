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
    PersistSelectedProductsRequest, PersistSelectedProductsResponse,
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
    Persiste con la misma estructura de extra_data que auto_persist
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

    # ── Extract fields from normalized Dropi product ──
    name = dropi_product.get("name", f"Dropi #{dropi_id}")[:255]
    image_url = dropi_product.get("image_url", "") or None
    stock = dropi_product.get("stock", 0)
    variations = dropi_product.get("variations", [])
    category = dropi_product.get("category", "")
    supplier = dropi_product.get("supplier", "")

    price_proveedor = float(dropi_product.get("price", 0))
    price_sugerido = float(dropi_product.get("suggested_price", 0)) or price_proveedor

    # USD approximation from suggested price
    price_usd = round(price_sugerido / 4200, 2) if price_sugerido > 0 else None

    # Margin calculation (suggested vs provider)
    margin_pct = round(((price_sugerido - price_proveedor) / price_sugerido) * 100, 1) if price_sugerido > 0 and price_proveedor > 0 else 0

    # Clean description from Dropi (strip HTML tags and entities)
    raw_desc = dropi_product.get("description", "")
    if raw_desc:
        import html
        description = html.unescape(re.sub(r'<[^>]+>', ' ', raw_desc))
        description = re.sub(r'\s+', ' ', description).strip()[:500]
    else:
        description = category or name

    # ── Build extra_data with SAME structure as auto_persist ──
    # This is what the frontend reads to render the rich product card
    extra_data = {
        "auto_persisted": True,
        "source": "dropi_import",
        "score_total": 0,
        "score_breakdown": {
            "ventas": 0,
            "margen": min(margin_pct, 100),
            "tendencia": 0,
            "competencia_inv": 0,
            "rating": 0,
        },
        "source_platform": "dropi",
        "source_url": f"https://app.dropi.co/dashboard/product-details/{dropi_id}/{name.lower().replace(' ', '-')}",
        "rating": 0,
        "monthly_sales": 0,
        "seller": supplier,
        "reviews_count": 0,
        "currency": "COP",
        # Dropi-specific extras (not rendered by card but useful)
        "dropi_import": True,
        "price_cop_proveedor": price_proveedor,
        "price_cop_sugerido": price_sugerido,
        "margin_pct": margin_pct,
        "stock": stock,
        "category": category,
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
    

# ── Persistencia selectiva de productos ──────────────────────────

@router.post("/persist-selected", response_model=PersistSelectedProductsResponse, status_code=status.HTTP_201_CREATED)
async def persist_selected_products(
    body: PersistSelectedProductsRequest,
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Persiste manualmente los productos que el usuario seleccionó desde el chat.
    Recibe una lista de hasta 10 productos con sus datos y los guarda en el catálogo.
    Los winners ya fueron autopersistidos; este endpoint es para los potenciales (score 50-74).
    """
    from app.use_cases.product.auto_persist import _normalize_product, _product_exists
    from domain.entities.product import Product

    created_ids: list[str] = []
    skipped_names: list[str] = []

    for item in body.products[:10]:
        item_dict = item.model_dump()

        # Forzar score al threshold mínimo para que _normalize_product los acepte
        # (los potenciales tienen score < 75 pero el usuario decidió guardarlos)
        item_dict["score_total"] = max(item_dict.get("score_total", 0), 75.0)

        normalized = _normalize_product(item_dict)
        if not normalized:
            skipped_names.append(item_dict.get("name", ""))
            continue

        if await _product_exists(session, org_id, normalized["name"]):
            skipped_names.append(normalized["name"])
            continue

        product = Product(
            organization_id=org_id,
            name=normalized["name"],
            description=normalized["description"],
            price_usd=normalized["price_usd"],
            image_url=normalized["image_url"],
            is_active=True,
            extra_data={
                **normalized["extra_data"],
                "manually_selected": True,  # marca que el user lo eligió manualmente
            },
        )
        session.add(product)
        await session.flush()
        created_ids.append(product.id)

    await session.commit()
    logger.info(f"persist-selected: created={len(created_ids)} skipped={len(skipped_names)} org={org_id}")
    return PersistSelectedProductsResponse(created_ids=created_ids, skipped_names=skipped_names)
