"""
Auto-persistencia de Productos Winners desde output del agente product_search.

ESTRATEGIA — JSON embebido:
El system prompt del product_search agent le indica que emita un bloque
<!--PRODUCT_JSON [{...}] --> al final de su respuesta markdown,
incluyendo SOLO productos con score >= 75 (winners).

Este módulo extrae ese JSON, valida duplicados por nombre+org,
y persiste los productos ganadores en la tabla `products`.

Fallback: si el bloque JSON no existe, se intenta extraer productos
directamente del `raw_scraped_data` que viene en el result del agente
(solo los que pasaron el threshold de scoring).
"""

from __future__ import annotations

import re
import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from domain.entities.product import Product

logger = logging.getLogger(__name__)

# ── Scoring threshold ────────────────────────────────────────────────────────

WINNER_THRESHOLD = 75.0


# ── Detection ────────────────────────────────────────────────────────────────

def has_product_json(content: str) -> bool:
    """Detecta si el output del agente contiene el bloque PRODUCT_JSON."""
    return bool(content and "<!--PRODUCT_JSON" in content)


# ── JSON Extraction (primary) ────────────────────────────────────────────────

def _extract_product_json(content: str) -> list[dict] | None:
    """
    Extrae el array JSON desde <!--PRODUCT_JSON [...] -->.
    Returns lista de dicts o None.
    """
    match = re.search(
        r'<!--\s*PRODUCT_JSON\s*(\[.*?\])\s*-->',
        content,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if isinstance(data, list) and len(data) > 0:
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse PRODUCT_JSON block: {e}")

    return None


# ── Selectable products extraction (Score 50-74) ─────────────────────────────

def extract_selectable_products(content: str) -> list[dict] | None:
    """
    Extrae productos potenciales (score 50-74) desde el bloque
    <!--SELECTABLE_PRODUCTS_JSON [...] --> del output del agente.

    Estos productos NO se autopersisten — el usuario elige cuáles guardar
    a través del componente ProductSelectionCard en el chat.
    """
    if not content or "<!--SELECTABLE_PRODUCTS_JSON" not in content:
        return None

    match = re.search(
        r'<!--\s*SELECTABLE_PRODUCTS_JSON\s*(\[.*?\])\s*-->',
        content,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if isinstance(data, list) and len(data) > 0:
            return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse SELECTABLE_PRODUCTS_JSON block: {e}")

    return None


# ── Fallback: extract from raw scraped data ──────────────────────────────────

def extract_winners_from_scraped(raw_scraped_data: dict) -> list[dict] | None:
    """
    Fallback: si el agente no emitió PRODUCT_JSON, intentamos extraer
    winners directamente del raw_scraped_data + scoring.

    Importa scoring aquí para evitar circular imports.
    """
    if not raw_scraped_data:
        return None

    from app.agents.scoring import score_products, filter_winners

    all_products = []

    def _num(value, default=0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    # Recopilar de todas las fuentes
    for source_key in ("mercadolibre", "google_shopping", "aliexpress", "amazon", "temu", "shopee"):
        source_data = raw_scraped_data.get(source_key, [])
        if not isinstance(source_data, list):
            continue
        for p in source_data:
            all_products.append({
                "name": p.get("name", ""),
                "price": _num(p.get("price")),
                "currency": p.get("currency", "COP"),
                "source": source_key,
                "monthly_sales": _num(p.get("sold_quantity")),
                "margin_pct": 0,
                "trend_growth_pct": 0,
                "competition_level": 5,
                "rating": _num(p.get("rating")),
                "seller": p.get("seller", "N/A"),
                "url": p.get("url", ""),
                "image_url": p.get("thumbnail") or p.get("image_url") or p.get("image", ""),
                "reviews_count": p.get("reviews_count", 0),
            })

    if not all_products:
        return None

    scored = score_products(all_products)
    winners = filter_winners(scored, threshold=WINNER_THRESHOLD)

    if not winners:
        return None

    # Normalizar al formato esperado por _normalize_product
    return [
        {
            "name": w.get("name", ""),
            "description": f"Score: {w.get('score_total', 0)}/100 | Source: {w.get('source', 'N/A')} | Rating: {w.get('rating', 'N/A')} | Est. Sales: {w.get('monthly_sales', 'N/A')}",
            "price_usd": _estimate_usd(w.get("price", 0), w.get("currency", "COP")),
            "image_url": w.get("image_url", ""),
            "source_url": _ensure_usable_url(
                w.get("url", ""),
                w.get("source", ""),
                w.get("name", ""),
            ),
            "source_platform": w.get("source", ""),
            "score_total": w.get("score_total", 0),
            "score_breakdown": w.get("score_breakdown", {}),
            "rating": w.get("rating", 0),
            "monthly_sales": w.get("monthly_sales", 0),
            "seller": w.get("seller", ""),
            "reviews_count": w.get("reviews_count", 0),
        }
        for w in winners
    ]


def _estimate_usd(price: float, currency: str) -> float | None:
    """Conversión aproximada a USD para referencia."""
    if price <= 0:
        return None

    # Tasas aproximadas — solo para referencia, no para transacciones
    rates = {
        "COP": 4200, "MXN": 17, "ARS": 900, "CLP": 930,
        "PEN": 3.7, "BRL": 5.0, "USD": 1,
    }
    rate = rates.get(currency.upper(), 1)
    if rate <= 0:
        return None
    return round(price / rate, 2)


# ── URL validation & fallback ────────────────────────────────────────────

def _is_usable_url(url: str) -> bool:
    """
    Verifica si una URL es realmente usable para el usuario final.
    Rechaza:
    - URLs internas de Google Shopping
    - URLs de búsqueda disfrazadas
    - URLs genéricas de dominio root (ej: "https://www.mercadolibre.com/")
      que el LLM inventa cuando no tiene el permalink real
    """
    if not url or not url.startswith("http"):
        return False

    # Patrones de URLs que sabemos que no funcionan
    bad_patterns = [
        "/shopping/product/",       # Google Shopping interna — "Nothing to see here"
        "google.com/shopping",      # Variantes de Google Shopping interna
        "google.com/url?",          # Google redirect wrapper
        "webcache.googleusercontent", # Google cache
    ]
    if any(p in url for p in bad_patterns):
        return False

    # Detectar URLs genéricas de dominio root que el LLM inventa
    # Ej: "https://www.mercadolibre.com/", "https://aliexpress.com",
    #     "https://www.amazon.com/", "https://www.temu.com/"
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    # Si el path está vacío o es solo "/" → es un dominio root, no un producto
    if not path:
        return False

    # Si el path es muy corto (< 5 chars) probablemente no es un producto real
    # Ej: "/es", "/co" son solo locales, no productos
    if len(path) < 5:
        return False

    return True


def _build_search_url(platform: str, product_name: str) -> str:
    """
    Genera una URL de búsqueda funcional en la plataforma para el producto.
    Es el fallback cuando no hay permalink directo confiable.
    """
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

    # Normalizar: el platform puede venir como "MercadoLibre", "Google Shopping", etc.
    platform_key = platform.lower().replace(" ", "_")
    return search_urls.get(platform_key, f"https://www.google.com/search?q={q}")


def _ensure_usable_url(url: str, platform: str, product_name: str) -> str:
    """
    Última línea de defensa: si la URL no es usable, genera un fallback
    de búsqueda en la plataforma correspondiente.
    """
    if _is_usable_url(url):
        return url
    return _build_search_url(platform, product_name)


# ── Normalize a single product ──────────────────────────────────────────────

def _normalize_product(item: dict) -> dict | None:
    """Valida y normaliza un dict de producto para persistencia."""
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

    # Robust image URL extraction — try multiple fields.
    # Bloquea imágenes que vengan del usuario (chat-uploads en S3 propio o
    # data URLs base64 de uploads efímeros). El image_url del producto
    # debe ser SIEMPRE la URL de la imagen scrapeada (CDN del marketplace).
    image_url = ""
    blocked_substrings = (
        "/chat-uploads/",            # bucket propio: imágenes subidas por usuario
        "nexom-creatives",           # safety: cualquier URL de nuestro bucket de creatives
    )
    for img_field in ("image_url", "thumbnail", "image", "gallery_url"):
        candidate = str(item.get(img_field, "")).strip()
        if not candidate:
            continue
        if candidate.startswith("data:"):
            continue  # data URL = upload efímero del usuario, nunca persistir
        if not candidate.startswith("http"):
            continue
        if len(candidate) > 512:
            continue
        if any(blocked in candidate for blocked in blocked_substrings):
            continue
        image_url = candidate
        break

    score_total = item.get("score_total", 0)
    try:
        score_total = float(score_total)
    except (ValueError, TypeError):
        score_total = 0

    # Solo persistir winners
    if score_total < WINNER_THRESHOLD:
        return None

    # Build source_url with validation
    raw_source_url = item.get("source_url") or item.get("url", "")
    source_platform = item.get("source_platform") or item.get("source", "")

    source_url = _ensure_usable_url(raw_source_url, source_platform, name)

    # Extra data con toda la metadata del scoring
    extra_data = {
        "auto_persisted": True,
        "source": "product_search_agent",
        "score_total": score_total,
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


# ── URL enrichment from raw scraped data ─────────────────────────────────

def _build_url_index(raw_scraped_data: dict) -> dict[str, dict]:
    """
    Construye un índice nombre_normalizado → {url, image_url, source}
    desde los datos reales del scraping para enriquecer items del LLM.
    """
    index: dict[str, dict] = {}

    for source_key in ("mercadolibre", "google_shopping", "aliexpress", "amazon", "temu", "shopee"):
        source_data = raw_scraped_data.get(source_key, [])
        if not isinstance(source_data, list):
            continue
        for p in source_data:
            name = str(p.get("name", "")).strip().lower()
            url = str(p.get("url", "")).strip()
            image = str(p.get("image_url") or p.get("thumbnail") or p.get("image", "")).strip()

            if not name or not url.startswith("http"):
                continue

            # Indexar por nombre completo y también por primeras 40 chars
            # para matching fuzzy con nombres que el LLM pudo truncar
            index[name] = {"url": url, "image_url": image, "source": source_key}
            short_key = name[:40]
            if short_key not in index:
                index[short_key] = {"url": url, "image_url": image, "source": source_key}

    return index


def _enrich_items_with_real_urls(items: list[dict], raw_scraped_data: dict) -> list[dict]:
    """
    Enriquece los items del PRODUCT_JSON del LLM con las URLs reales
    del scraping. El LLM frecuentemente inventa URLs o pone URLs de
    búsqueda en vez del permalink del producto.
    """
    url_index = _build_url_index(raw_scraped_data)
    if not url_index:
        return items

    enriched = []
    for item in items:
        item = dict(item)  # no mutar original
        name = str(item.get("name", "")).strip().lower()
        source_url = str(item.get("source_url") or item.get("url", "")).strip()

        # La URL del LLM es sospechosa si:
        # - no empieza con http
        # - es una URL de búsqueda (contiene "search", "q=", "query")
        # - tiene el patrón de URL construida (nombre URL-encoded en la path)
        # - es una URL interna de Google Shopping que no funciona
        url_suspect = (
            not source_url.startswith("http")
            or "search" in source_url.lower()
            or "q=" in source_url
            or "query" in source_url.lower()
            or "/shopping/product/" in source_url
            or "google.com/shopping" in source_url
        )

        if url_suspect or not source_url:
            # Intentar match exacto por nombre
            match = url_index.get(name)

            # Fallback: match por primeros 40 chars
            if not match:
                match = url_index.get(name[:40])

            # Fallback: buscar por substring en ambas direcciones
            if not match:
                for idx_name, idx_data in url_index.items():
                    if name in idx_name or idx_name in name:
                        match = idx_data
                        break

            if match:
                item["source_url"] = match["url"]
                # También enriquecer imagen si no tiene
                if not item.get("image_url") and match.get("image_url"):
                    item["image_url"] = match["image_url"]
                # Enriquecer source_platform si no tiene
                if not item.get("source_platform") and match.get("source"):
                    item["source_platform"] = match["source"]

        enriched.append(item)

    return enriched


# ── Main auto-persist function ──────────────────────────────────────────────

async def auto_persist_winner_products(
    session: AsyncSession,
    content: str,
    org_id: str,
    conversation_id: str | None = None,
    raw_scraped_data: dict | None = None,
) -> list[str]:
    """
    Detecta y persiste productos ganadores (score ≥ 75) desde el output
    del agente product_search.

    Fuentes (en orden de prioridad):
    1. Bloque <!--PRODUCT_JSON [...] --> en el content del agente
    2. Fallback: raw_scraped_data con scoring aplicado

    Returns: lista de product IDs creados.
    """
    items: list[dict] | None = None

    # Estrategia 1: JSON embebido en el content
    if has_product_json(content):
        items = _extract_product_json(content)
        if items:
            logger.info(f"Extracted {len(items)} products from PRODUCT_JSON block")
            # Enriquecer URLs del LLM con las reales del scraping
            if raw_scraped_data:
                items = _enrich_items_with_real_urls(items, raw_scraped_data)

    # Estrategia 2: Fallback desde datos scrapeados (ya tiene URLs reales)
    if not items and raw_scraped_data:
        items = extract_winners_from_scraped(raw_scraped_data)
        if items:
            logger.info(f"Extracted {len(items)} winners from raw scraped data (fallback)")

    if not items:
        return []

    created_ids = []

    for item in items[:10]:  # Max 10 productos por response
        normalized = _normalize_product(item)
        if not normalized:
            continue

        # Dedup: no crear si ya existe un producto con el mismo nombre
        if await _product_exists(session, org_id, normalized["name"]):
            logger.debug(f"Product '{normalized['name']}' already exists in org {org_id}, skipping")
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
            f"Auto-created {len(created_ids)} winner products "
            f"for org {org_id} from conversation {conversation_id}"
        )

    return created_ids