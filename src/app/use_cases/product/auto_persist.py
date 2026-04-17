"""
Extracción y persistencia manual de productos desde output del agente product_search.

El agente emite un único bloque <!--CANDIDATE_PRODUCTS_JSON [...] --> con
hasta 20 productos. El frontend muestra el selector y el usuario decide
cuáles persistir vía el endpoint /persist-selected.

Este módulo expone:
- extract_candidate_products(content): parsea el bloque del output del agente
- has_candidate_json(content): detecta si el bloque existe
- _normalize_product(item): valida y normaliza un producto para persistencia
  (usado tanto por el endpoint como por el flujo de resume-with-selection)
"""

from __future__ import annotations

import re
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from domain.entities.product import Product

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────

MAX_CANDIDATES = 20
WINNER_THRESHOLD = 75.0
POTENTIAL_THRESHOLD = 50.0


def _bucket_for_score(score: float) -> str:
    """Clasifica un score en su bucket. Se usa para extra_data.bucket."""
    if score >= WINNER_THRESHOLD:
        return "winner"
    if score >= POTENTIAL_THRESHOLD:
        return "potential"
    return "rejected"


# ── Detection ────────────────────────────────────────────────────────────────

def has_candidate_json(content: str) -> bool:
    """Detecta si el output del agente contiene el bloque CANDIDATE_PRODUCTS_JSON."""
    return bool(content and "<!--CANDIDATE_PRODUCTS_JSON" in content)


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_candidate_products(content: str) -> list[dict] | None:
    """
    Extrae el array JSON desde <!--CANDIDATE_PRODUCTS_JSON [...] -->.
    Retorna una lista de dicts (máximo MAX_CANDIDATES) o None.

    Estos productos NO se autopersisten — el usuario elige cuáles guardar
    a través del componente ProductSelectionCard en el chat/flow.
    """
    if not content or "<!--CANDIDATE_PRODUCTS_JSON" not in content:
        return None

    match = re.search(
        r'<!--\s*CANDIDATE_PRODUCTS_JSON\s*(\[.*?\])\s*-->',
        content,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse CANDIDATE_PRODUCTS_JSON block: {e}")
        return None

    if not isinstance(data, list) or not data:
        return None

    # Hard cap: nunca más de MAX_CANDIDATES aunque el LLM se exceda.
    # Sort by score_total desc para quedarnos con los mejores si hay exceso.
    data_sorted = sorted(
        data,
        key=lambda x: float(x.get("score_total", 0) or 0),
        reverse=True,
    )
    return data_sorted[:MAX_CANDIDATES]


# ── URL validation & fallback ────────────────────────────────────────────

def _is_usable_url(url: str) -> bool:
    """
    Verifica si una URL es realmente usable para el usuario final.
    Rechaza:
    - URLs internas de Google Shopping
    - URLs de búsqueda disfrazadas
    - URLs genéricas de dominio root que el LLM inventa
    """
    if not url or not url.startswith("http"):
        return False

    bad_patterns = [
        "/shopping/product/",
        "google.com/shopping",
        "google.com/url?",
        "webcache.googleusercontent",
    ]
    if any(p in url for p in bad_patterns):
        return False

    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    if not path:
        return False
    if len(path) < 5:
        return False

    return True


def _build_search_url(platform: str, product_name: str) -> str:
    """Fallback: URL de búsqueda en la plataforma cuando no hay permalink confiable."""
    from urllib.parse import quote_plus
    q = quote_plus(product_name)

    search_urls = {
        "mercadolibre":    f"https://listado.mercadolibre.com.co/{q}",
        "google_shopping": f"https://www.google.com/search?q={q}&udm=28",
        "aliexpress":      f"https://www.aliexpress.com/w/wholesale-{q}.html",
        "amazon":          f"https://www.amazon.com/s?k={q}",
        "temu":            f"https://www.temu.com/search_result.html?search_key={q}",
        "shopee":          f"https://shopee.com.co/search?keyword={q}",
    }

    platform_key = platform.lower().replace(" ", "_") if platform else ""
    return search_urls.get(platform_key, f"https://www.google.com/search?q={q}")


def _ensure_usable_url(url: str, platform: str, product_name: str) -> str:
    """Si la URL no es usable, genera un fallback de búsqueda."""
    if _is_usable_url(url):
        return url
    return _build_search_url(platform, product_name)


# ── Normalize a single product ──────────────────────────────────────────────

def _normalize_product(item: dict) -> dict | None:
    """
    Valida y normaliza un dict de producto para persistencia.

    A diferencia de la versión anterior, NO filtra por score — cualquier
    score es válido. Se guarda el score real en extra_data y se clasifica
    el bucket (winner/potential/rejected) según el threshold.
    """
    name = str(item.get("name", "")).strip()
    if not name or len(name) < 3:
        return None

    name = name[:255]

    description = item.get("description", "")
    if isinstance(description, str) and len(description) > 2000:
        description = description[:2000]

    price_usd = None
    raw_price = item.get("price_usd") or item.get("price")
    if raw_price is not None:
        try:
            price_usd = round(float(raw_price), 2)
            if price_usd <= 0:
                price_usd = None
        except (ValueError, TypeError):
            pass

    # Bloquea imágenes del usuario (chat uploads, data URLs efímeras).
    image_url = ""
    blocked_substrings = (
        "/chat-uploads/",
        "nexom-creatives",
    )
    for img_field in ("image_url", "thumbnail", "image", "gallery_url"):
        candidate = str(item.get(img_field, "")).strip()
        if not candidate:
            continue
        if candidate.startswith("data:"):
            continue
        if not candidate.startswith("http"):
            continue
        if len(candidate) > 512:
            continue
        if any(blocked in candidate for blocked in blocked_substrings):
            continue
        image_url = candidate
        break

    # Score real — sin forzar a un threshold, se guarda tal cual.
    try:
        score_total = float(item.get("score_total", 0) or 0)
    except (ValueError, TypeError):
        score_total = 0.0

    # Bucket: prioriza el valor que mande el LLM, pero si no viene o es
    # inconsistente, lo recomputa a partir del score.
    raw_bucket = str(item.get("bucket", "")).lower().strip()
    if raw_bucket not in ("winner", "potential", "rejected"):
        raw_bucket = _bucket_for_score(score_total)
    else:
        # Safety: si el LLM dice "winner" pero el score es 40, corregimos.
        computed = _bucket_for_score(score_total)
        if raw_bucket != computed:
            raw_bucket = computed

    raw_source_url = item.get("source_url") or item.get("url", "")
    source_platform = item.get("source_platform") or item.get("source", "")
    source_url = _ensure_usable_url(raw_source_url, source_platform, name)

    extra_data = {
        "source": "product_search_agent",
        "bucket": raw_bucket,                    # winner | potential | rejected
        "score_total": score_total,              # score REAL, no forzado
        "score_breakdown": item.get("score_breakdown", {}),
        "source_platform": source_platform,
        "source_url": source_url,
        "rating": item.get("rating"),
        "monthly_sales": item.get("monthly_sales"),
        "seller": item.get("seller", ""),
        "reviews_count": item.get("reviews_count", 0),
        "currency": item.get("currency", ""),
    }

    return {
        "name": name,
        "description": description or None,
        "price_usd": price_usd,
        "image_url": image_url or None,
        "extra_data": extra_data,
    }


# ── Dedup check ──────────────────────────────────────────────────────────────

async def _product_exists(session: AsyncSession, org_id: str, name: str) -> bool:
    """Verifica si ya existe un producto con el mismo nombre (case-insensitive) en la org."""
    stmt = (
        select(func.count())
        .select_from(Product)
        .where(
            Product.organization_id == org_id,
            func.lower(Product.name) == name.lower().strip(),
            Product.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    return (result.scalar() or 0) > 0


# ── Persist a list of manually selected products ────────────────────────────

async def persist_selected_candidates(
    session: AsyncSession,
    items: list[dict],
    org_id: str,
) -> tuple[list[str], list[str]]:
    """
    Persiste una lista de productos que el usuario eligió manualmente.

    Retorna (created_ids, skipped_names).

    Esta función centraliza la lógica para que pueda ser usada tanto desde
    el endpoint /persist-selected como desde /flows/{id}/resume-with-selection.
    """
    created_ids: list[str] = []
    skipped_names: list[str] = []

    # ── Resource limit check ──
    from app.use_cases.resource_limits import count_resources, RESOURCE_LIMITS
    current_count = await count_resources(session, org_id, "products")
    limit = RESOURCE_LIMITS.get("products", 400)
    available_slots = max(0, limit - current_count)
    if available_slots == 0:
        logger.warning(f"Product persist skipped for org {org_id}: resource limit reached ({current_count}/{limit})")
        for item in items[:MAX_CANDIDATES]:
            skipped_names.append(str(item.get("name", ""))[:120] or "(limit reached)")
        return created_ids, skipped_names

    for item in items[:min(MAX_CANDIDATES, available_slots)]:
        normalized = _normalize_product(item)
        if not normalized:
            skipped_names.append(str(item.get("name", ""))[:120] or "(unnamed)")
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
            extra_data=normalized["extra_data"],
        )
        session.add(product)
        await session.flush()
        created_ids.append(product.id)

    if created_ids:
        logger.info(
            f"Persisted {len(created_ids)} user-selected products for org {org_id} "
            f"(skipped {len(skipped_names)} duplicates/invalid)"
        )

    return created_ids, skipped_names
