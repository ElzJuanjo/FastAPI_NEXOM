"""
Cliente de MercadoLibre vía SerpAPI.
Usa Google Search con site:mercadolibre.com.xx para obtener listings reales.
"""

from __future__ import annotations

import re
from typing import Optional

import httpx

from infra.config.database import settings


class MercadoLibreClient:

    SERPAPI_URL = "https://serpapi.com/search"

    # Dominios por país
    DOMAINS = {
        "colombia": "mercadolibre.com.co",
        "mexico": "mercadolibre.com.mx",
        "argentina": "mercadolibre.com.ar",
        "chile": "mercadolibre.cl",
        "peru": "mercadolibre.com.pe",
        "brasil": "mercadolivre.com.br",
        "ecuador": "mercadolibre.com.ec",
    }

    COUNTRY_CODES = {
        "colombia": "co",
        "mexico": "mx",
        "argentina": "ar",
        "chile": "cl",
        "peru": "pe",
        "brasil": "br",
        "ecuador": "ec",
    }

    async def search_products(
        self,
        query: str,
        country: str = "colombia",
        limit: int = 10,
        sort: str = "relevance",
    ) -> list[dict]:
        """
        Busca productos en MercadoLibre usando SerpAPI (Google site: search).
        """
        if not settings.SERPAPI_API_KEY:
            return []

        domain = self.DOMAINS.get(country.lower(), "mercadolibre.com.co")
        gl = self.COUNTRY_CODES.get(country.lower(), "co")

        params = {
            "engine": "google",
            "q": f"site:{domain} {query}",
            "gl": gl,
            "hl": "es",
            "num": min(limit, 20),
            "api_key": settings.SERPAPI_API_KEY,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.SERPAPI_URL, params=params)

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for item in data.get("organic_results", []):
            url = item.get("link", "")

            # Solo listings reales de ML (filtrar páginas de categoría, etc.)
            if not self._is_product_url(url, domain):
                continue

            price = self._extract_price(item)
            currency = self._get_currency(country)

            results.append({
                "source": "mercadolibre",
                "name": self._clean_title(item.get("title", "")),
                "price": price,
                "currency": currency,
                "url": url,
                "image_url": item.get("thumbnail", ""),
                "snippet": item.get("snippet", ""),
                "seller": self._extract_seller(item),
                "sold_quantity": self._extract_sold(item),
                "condition": "",
                "available_quantity": 0,
                "free_shipping": self._has_free_shipping(item),
            })

        return results

    async def get_category_trends(
        self,
        category_id: str,
        country: str = "colombia",
    ) -> list[dict]:
        """Obtiene tendencias buscando categorías populares."""
        if not settings.SERPAPI_API_KEY:
            return []

        domain = self.DOMAINS.get(country.lower(), "mercadolibre.com.co")
        gl = self.COUNTRY_CODES.get(country.lower(), "co")

        params = {
            "engine": "google",
            "q": f"site:{domain} {category_id} más vendidos",
            "gl": gl,
            "hl": "es",
            "num": 10,
            "api_key": settings.SERPAPI_API_KEY,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.SERPAPI_URL, params=params)

        if response.status_code != 200:
            return []

        data = response.json()
        return [
            {"title": r.get("title", ""), "url": r.get("link", "")}
            for r in data.get("organic_results", [])
        ]

    async def get_product_details(self, item_id: str) -> Optional[dict]:
        """No disponible sin API auth — retorna None."""
        return None

    # ---------------------------------------------------------------------------
    # Helpers privados
    # ---------------------------------------------------------------------------

    def _is_product_url(self, url: str, domain: str) -> bool:
        """Verifica si la URL es de un producto (no categoría ni home)."""
        if domain not in url:
            return False
        # URLs de producto de ML suelen tener MCO-, MLA-, MLM- etc.
        product_patterns = [
            r"MCO-\d+", r"MLA-\d+", r"MLM-\d+", r"MLC-\d+",
            r"MPE-\d+", r"MLB-\d+", r"MEC-\d+",
            r"/p/", r"\.com\.\w+/\w+-\w+",
        ]
        return any(re.search(p, url) for p in product_patterns)

    def _clean_title(self, title: str) -> str:
        """Limpia el título removiendo sufijos de ML."""
        # Remover " | MercadoLibre", " - MercadoLibre" etc.
        for suffix in [" | MercadoLibre", " - MercadoLibre", " | Mercado Libre", " - Mercado Libre"]:
            title = title.replace(suffix, "")
        return title.strip()

    def _extract_price(self, item: dict) -> float:
        """Intenta extraer precio del snippet o rich_snippet."""
        # SerpAPI a veces incluye precio en rich_snippet
        rich = item.get("rich_snippet", {})
        if isinstance(rich, dict):
            # Buscar en detected_extensions o top
            top = rich.get("top", {})
            if isinstance(top, dict):
                price = top.get("detected_extensions", {}).get("price", 0)
                if price:
                    return float(price)

        # Intentar extraer del snippet con regex
        snippet = item.get("snippet", "")
        price_match = re.search(r"\$\s?([\d.,]+)", snippet)
        if price_match:
            price_str = price_match.group(1).replace(".", "").replace(",", ".")
            try:
                return float(price_str)
            except ValueError:
                pass

        return 0.0

    def _extract_seller(self, item: dict) -> str:
        """Extrae nombre del vendedor si está disponible."""
        snippet = item.get("snippet", "")
        seller_match = re.search(r"(?:por|vendido por|seller:)\s*(\w+)", snippet, re.IGNORECASE)
        return seller_match.group(1) if seller_match else ""

    def _extract_sold(self, item: dict) -> int:
        """Extrae cantidad vendida del snippet o title."""
        # Check both snippet and title for sales data
        text = (item.get("snippet", "") + " " + item.get("title", "")).lower()

        # Format: "500+ vendidos", "1.234 vendidos", "+500 vendidos"
        sold_match = re.search(r"\+?(\d[\d.,]*)(?:\+)?\s*vendidos?", text, re.IGNORECASE)
        if sold_match:
            try:
                num_str = sold_match.group(1).replace(".", "").replace(",", "")
                return int(num_str)
            except ValueError:
                pass

        # Format: "sold 500+", "500+ sold"
        sold_match_en = re.search(r"(\d[\d.,]*)\+?\s*sold", text, re.IGNORECASE)
        if sold_match_en:
            try:
                num_str = sold_match_en.group(1).replace(".", "").replace(",", "")
                return int(num_str)
            except ValueError:
                pass

        # Format: "Más de 500 vendidos" or "más de 25 mil vendidos"
        mas_match = re.search(r"más de\s+(\d[\d.,]*)\s*(mil)?\s*vendidos?", text, re.IGNORECASE)
        if mas_match:
            try:
                num_str = mas_match.group(1).replace(".", "").replace(",", "")
                multiplier = 1000 if mas_match.group(2) else 1
                return int(num_str) * multiplier
            except ValueError:
                pass

        # Format in rich snippet: "reviews_count" often correlates with sales
        rich = item.get("rich_snippet", {})
        if isinstance(rich, dict):
            reviews = rich.get("top", {}).get("detected_extensions", {}).get("reviews", 0)
            if reviews and int(reviews) > 10:
                # Estimate: reviews ≈ 5-10% of sales
                return int(reviews) * 5

        return 0

    def _has_free_shipping(self, item: dict) -> bool:
        """Detecta envío gratis en el snippet."""
        snippet = item.get("snippet", "").lower()
        return "envío gratis" in snippet or "envio gratis" in snippet

    def _get_currency(self, country: str) -> str:
        currencies = {
            "colombia": "COP",
            "mexico": "MXN",
            "argentina": "ARS",
            "chile": "CLP",
            "peru": "PEN",
            "brasil": "BRL",
            "ecuador": "USD",
        }
        return currencies.get(country.lower(), "COP")


mercadolibre_client = MercadoLibreClient()