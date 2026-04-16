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
    name = (dropi_product.get("name") or "").strip()
    price_proveedor = float(dropi_product.get("price", 0) or 0)

    # Validación reforzada: la API de Dropi puede retornar un dict con
    # estructura válida pero datos vacíos para IDs que no existen
    # (name="", price=0). Eso no es un producto real.
    if not name or price_proveedor <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto Dropi #{dropi_id} no encontrado o sin datos válidos (sin nombre o sin precio)",
        )

    name = name[:255]
    image_url = dropi_product.get("image_url", "") or None
    stock = dropi_product.get("stock", 0)
    variations = dropi_product.get("variations", [])
    category = dropi_product.get("category", "")
    supplier = dropi_product.get("supplier", "")

    price_sugerido = float(dropi_product.get("suggested_price", 0) or 0) or price_proveedor

    # USD approximation from suggested price
    price_usd = round(price_sugerido / 4200, 2) if price_sugerido > 0 else None

    # Margin calculation (suggested vs provider)
    margin_pct = round(((price_sugerido - price_proveedor) / price_sugerido) * 100, 1) if price_sugerido > 0 and price_proveedor > 0 else 0

    # Clean description from Dropi (strip HTML tags and entities)
    raw_desc = dropi_product.get("description", "")
    if raw_desc:
        import html
        description = html.unescape(re.sub(r'<[^>]+>', ' ', raw_desc))
        description = re.sub(r'\s+', ' ', description).strip()
    else:
        description = category or name

    # ── Calculate a meaningful score from Dropi data ──
    # Dropi doesn't have sales/trend/competition data, but we do have margin
    # and stock which are strong signals. We align with the general scoring
    # system (scoring.py) using the same component weights where data exists.
    # Components without data use neutral baselines (same as score_product).
    from app.agents.scoring import normalize

    # Margin score (weight 0.25 in general scoring) — we HAVE this data
    margin_score = normalize(margin_pct, 0, 80) if margin_pct > 0 else 0.0
    margin_has_data = margin_pct > 0

    # Stock as a proxy for demand/availability (maps to sales weight 0.30)
    # High stock = supplier is confident in demand
    stock_score = normalize(stock, 0, 2000) if stock > 0 else 0.0
    stock_has_data = stock > 0

    # Rating, trend, competition: no data from Dropi → neutral baseline
    rating_score = 50.0
    trend_score = 50.0
    competition_score = 50.0

    # Calculate score using real data normalized + neutral baselines
    # Same formula: (Sales×0.30) + (Margin×0.25) + (Trend×0.20) + (Comp×0.15) + (Rating×0.10)
    raw_score = (
        stock_score * 0.30
        + margin_score * 0.25
        + trend_score * 0.20
        + competition_score * 0.15
        + rating_score * 0.10
    )

    # If we have real data for at least margin OR stock, apply a mild boost
    # to avoid the "everything is 50" effect of pure neutral baselines.
    # This mirrors the v3 blending logic in scoring.py.
    real_weight = (0.25 if margin_has_data else 0) + (0.30 if stock_has_data else 0)
    if real_weight >= 0.25:
        real_sum = (margin_score * 0.25 if margin_has_data else 0) + (stock_score * 0.30 if stock_has_data else 0)
        normalized_real = real_sum / real_weight if real_weight > 0 else 0
        blend = min(1.0, real_weight / 0.55 * 0.4 + 0.3)
        dropi_score = round(min(normalized_real * blend + raw_score * (1 - blend), 100.0), 1)
    else:
        dropi_score = round(min(raw_score, 100.0), 1)

    # Bucket classification (aligned with general thresholds)
    if dropi_score >= 75:
        dropi_bucket = "winner"
    elif dropi_score >= 50:
        dropi_bucket = "potential"
    else:
        dropi_bucket = "dropi"  # keep dropi tag for UI differentiation

    # ── Build extra_data with SAME structure as auto_persist ──
    # This is what the frontend reads to render the rich product card
    extra_data = {
        "source": "dropi_import",
        "bucket": dropi_bucket,
        "score_total": dropi_score,
        "score_breakdown": {
            "ventas": round(stock_score, 1),
            "margen": round(margin_score, 1),
            "tendencia": round(trend_score, 1),
            "competencia_inv": round(competition_score, 1),
            "rating": round(rating_score, 1),
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
        "data_coverage": round(real_weight, 2),
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
    Persiste manualmente los productos que el usuario seleccionó desde el chat o flow.

    Recibe una lista de hasta 20 productos con sus datos y los guarda en el catálogo
    con su score REAL y su bucket de clasificación (winner/potential/
    rejected) preservado en extra_data para que la página de Productos pueda filtrarlos
    correctamente.
    """
    from app.use_cases.product.auto_persist import persist_selected_candidates

    items = [item.model_dump() for item in body.products]
    created_ids, skipped_names = await persist_selected_candidates(
        session=session,
        items=items,
        org_id=org_id,
    )

    await session.commit()
    logger.info(f"persist-selected: created={len(created_ids)} skipped={len(skipped_names)} org={org_id}")
    return PersistSelectedProductsResponse(created_ids=created_ids, skipped_names=skipped_names)