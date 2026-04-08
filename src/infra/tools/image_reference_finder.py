"""
Image Reference Finder — busca fotos reales de productos en la web.

Usa Bing Images (scraping ligero) para encontrar imágenes de referencia
del producto real. No requiere API key ni créditos.

Flujo:
1. Usuario pide "genera imagen de un rolex pikachu"
2. Este módulo busca "rolex pikachu watch product photo" en Bing Images
3. Retorna la URL de la mejor imagen real encontrada
4. El image_gen_agent la descarga y la inyecta como referencia multimodal
5. Gemini genera la imagen BASADA en el producto real

Fallbacks: Bing Images → Google Images thumbnails → None
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BING_IMAGES_URL = "https://www.bing.com/images/search"
GOOGLE_IMAGES_URL = "https://www.google.com/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# Skip these domains — they're not product images
SKIP_DOMAINS = [
    "gstatic.com", "google.com", "googleapis.com", "bing.com",
    "bing.net", "microsoft.com", "favicon", "icon", "logo",
    "placeholder", "pixel", "spacer", "blank", "avatar",
    "profile", "badge", "emoji",
]

# Prefer these domains — likely real product images
PREFER_DOMAINS = [
    "amazon.com", "mercadolibre", "shopify", "ebay.com",
    "chrono24.com", "aliexpress", "walmart.com", "etsy.com",
    "cloudfront.net", "shopee", "lazada", "target.com",
    "bestbuy.com", "cdninstagram",
]


def _clean_query_for_image_search(user_input: str) -> str:
    """
    Clean the user's input into a good image search query.
    Remove instruction verbs, keep the product description.
    """
    query = user_input.strip()

    # Remove common instruction prefixes (ES/EN/PT)
    prefixes = [
        "genera una imagen de", "genera una foto de", "genera un creativo de",
        "crea una imagen de", "crea una foto de", "hazme una imagen de",
        "generate an image of", "create an image of", "make an image of",
        "generate a photo of", "create a photo of",
        "gerar uma imagem de", "criar uma imagem de",
        "genera", "generate", "create", "crea", "hazme", "make",
        "imagen de", "image of", "foto de", "photo of",
    ]
    query_lower = query.lower()
    for prefix in prefixes:
        if query_lower.startswith(prefix):
            query = query[len(prefix):].strip()
            break

    # Add "product photo" to improve search quality
    if len(query) < 100:
        query = f"{query} product photo real"

    return query


def _is_valid_image_url(url: str) -> bool:
    """Check if URL looks like a real product image."""
    if not url or len(url) < 20 or len(url) > 2000:
        return False

    url_lower = url.lower()

    # Must be HTTPS
    if not url_lower.startswith("https://"):
        return False

    # Skip known non-product domains
    if any(skip in url_lower for skip in SKIP_DOMAINS):
        return False

    # Must look like an image
    has_image_ext = any(
        ext in url_lower
        for ext in [".jpg", ".jpeg", ".png", ".webp", "image", "/img/", "/photo/"]
    )

    return has_image_ext or "?" in url  # Dynamic image URLs often have query params


def _score_image_url(url: str) -> int:
    """Score an image URL — higher is better for product reference."""
    score = 0
    url_lower = url.lower()

    # Prefer e-commerce domains
    if any(d in url_lower for d in PREFER_DOMAINS):
        score += 10

    # Prefer larger images (URL hints)
    if any(kw in url_lower for kw in ["large", "xlarge", "original", "full", "1024", "800"]):
        score += 5
    if any(kw in url_lower for kw in ["thumb", "small", "tiny", "mini", "icon", "32", "64"]):
        score -= 5

    # Prefer .jpg/.png (real photos) over .webp (often compressed)
    if ".jpg" in url_lower or ".jpeg" in url_lower:
        score += 2
    if ".png" in url_lower:
        score += 1

    return score


async def find_product_reference_image(
    user_input: str,
    max_results: int = 1,
) -> Optional[str]:
    """
    Search the web for a real photo of the product described in user_input.
    Returns the URL of the best matching real product image, or None.

    This function tries multiple sources:
    1. Bing Images (most reliable for scraping)
    2. Google Images thumbnails (fallback)
    """
    query = _clean_query_for_image_search(user_input)
    logger.info(f"Searching reference image for: '{query[:60]}'")

    # Try Bing Images first
    url = await _search_bing_images(query)
    if url:
        logger.info(f"Found reference image (Bing): {url[:80]}")
        return url

    # Fallback: Google Images
    url = await _search_google_images(query)
    if url:
        logger.info(f"Found reference image (Google): {url[:80]}")
        return url

    logger.warning(f"No reference image found for: '{query[:60]}'")
    return None


async def _search_bing_images(query: str) -> Optional[str]:
    """
    Search Bing Images and extract full-size image URLs.
    Bing embeds image URLs in the 'murl' attribute of result elements.
    """
    try:
        params = {
            "q": query,
            "form": "HDRSC2",
            "first": "1",
        }

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(
                BING_IMAGES_URL,
                params=params,
                headers=HEADERS,
            )

        if response.status_code != 200:
            logger.warning(f"Bing Images returned {response.status_code}")
            return None

        html = response.text

        # Extract full-size image URLs from Bing's murl attribute
        murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)

        # Also try JSON-style murl
        if not murls:
            murls = re.findall(r'"murl":"(https?://[^"]+)"', html)

        # Filter and score
        candidates = []
        for url in murls:
            # Unescape HTML entities
            url = url.replace("&amp;", "&")
            if _is_valid_image_url(url):
                candidates.append((url, _score_image_url(url)))

        if not candidates:
            # Fallback: try Bing thumbnail URLs (lower quality but reliable)
            thumbs = re.findall(
                r'src="(https://tse\d+\.mm\.bing\.net/th\?[^"]+)"',
                html,
            )
            if thumbs:
                # Bing thumbnails are OK as reference — model can still see the product
                return thumbs[0].replace("&amp;", "&")

            return None

        # Sort by score, return best
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    except Exception as e:
        logger.warning(f"Bing Images search error: {e}")
        return None


async def _search_google_images(query: str) -> Optional[str]:
    """
    Fallback: search Google Images for thumbnail references.
    Google heavily blocks scraping, so we extract whatever is available.
    """
    try:
        params = {
            "q": query,
            "tbm": "isch",
            "hl": "en",
        }

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(
                GOOGLE_IMAGES_URL,
                params=params,
                headers=HEADERS,
            )

        if response.status_code != 200:
            return None

        html = response.text

        # Try to find image URLs in various Google patterns
        patterns = [
            # Full-size URLs in JSON data
            r'\["(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)",\d+,\d+\]',
            # Image URLs in data attributes
            r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png))"',
            # Thumbnail URLs (last resort)
            r'src="(https://encrypted-tbn\d+\.gstatic\.com/images\?[^"]+)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html)
            valid = [u for u in matches if _is_valid_image_url(u)]
            if valid:
                return valid[0].replace("&amp;", "&")

        return None

    except Exception as e:
        logger.warning(f"Google Images search error: {e}")
        return None
