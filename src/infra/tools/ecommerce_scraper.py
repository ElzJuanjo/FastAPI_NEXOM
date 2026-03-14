"""
Cliente multi-fuente de E-Commerce vía SerpAPI.
Busca productos en AliExpress, Amazon, Temu y Shopee usando Google site: search.
"""

from __future__ import annotations

import re
from typing import Optional

import httpx

from infra.config.database import settings


class EcommerceScraperClient:

    SERPAPI_URL = "https://serpapi.com/search"

    # Configuración por fuente
    SOURCES = {
        "aliexpress": {
            "domain": "aliexpress.com",
            "currency_default": "USD",
            "product_patterns": [r"/item/", r"/\d+\.html"],
        },
        "amazon": {
            "domains": {
                "us": "amazon.com",
                "mexico": "amazon.com.mx",
                "brasil": "amazon.com.br",
                "colombia": "amazon.com",
                "argentina": "amazon.com",
                "chile": "amazon.com",
                "peru": "amazon.com",
            },
            "currency_default": "USD",
            "currencies": {
                "mexico": "MXN",
                "brasil": "BRL",
            },
            "product_patterns": [r"/dp/[A-Z0-9]+", r"/gp/product/"],
        },
        "temu": {
            "domain": "temu.com",
            "currency_default": "USD",
            "product_patterns": [r"/[a-z0-9-]+-g-\d+", r"/goods"],
        },
        "shopee": {
            "domains": {
                "colombia": "shopee.com.co",
                "mexico": "shopee.com.mx",
                "brasil": "shopee.com.br",
                "chile": "shopee.cl",
            },
            "currency_default": "COP",
            "currencies": {
                "colombia": "COP",
                "mexico": "MXN",
                "brasil": "BRL",
                "chile": "CLP",
            },
            "product_patterns": [r"/\w+-i\.\d+\.\d+"],
        },
    }

    COUNTRY_CODES = {
        "colombia": "co", "mexico": "mx", "argentina": "ar",
        "chile": "cl", "peru": "pe", "brasil": "br", "ecuador": "ec",
        "us": "us",
    }

    async def search(
        self,
        source: str,
        query: str,
        country: str = "colombia",
        limit: int = 10,
    ) -> list[dict]:
        """
        Busca productos en la fuente especificada vía SerpAPI.

        Args:
            source: aliexpress, amazon, temu, shopee
            query: Término de búsqueda
            country: País del usuario
            limit: Máximo de resultados
        """
        if not settings.SERPAPI_API_KEY:
            return []

        source_config = self.SOURCES.get(source.lower())
        if not source_config:
            return []

        domain = self._get_domain(source, country, source_config)
        gl = self.COUNTRY_CODES.get(country.lower(), "co")

        params = {
            "engine": "google",
            "q": f"site:{domain} {query}",
            "gl": gl,
            "hl": "es",
            "num": min(limit, 15),
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

            if not self._is_product_url(url, domain, source_config.get("product_patterns", [])):
                continue

            price = self._extract_price(item)
            currency = self._get_currency(source, country, source_config)

            results.append({
                "source": source,
                "name": self._clean_title(item.get("title", ""), source),
                "price": price,
                "currency": currency,
                "url": url,
                "image_url": item.get("thumbnail", ""),
                "snippet": item.get("snippet", ""),
                "rating": self._extract_rating(item),
                "reviews_count": self._extract_reviews(item),
                "seller": self._extract_seller(item, source),
            })

        return results

    async def search_all(
        self,
        query: str,
        country: str = "colombia",
        sources: list[str] | None = None,
        limit_per_source: int = 8,
    ) -> dict[str, list[dict]]:
        """
        Busca en múltiples fuentes simultáneamente.

        Returns:
            Dict con key=source, value=lista de productos
        """
        if sources is None:
            sources = ["aliexpress", "amazon", "temu", "shopee"]

        results = {}
        for source in sources:
            try:
                products = await self.search(
                    source=source,
                    query=query,
                    country=country,
                    limit=limit_per_source,
                )
                results[source] = products
            except Exception as e:
                results[source] = []
                results[f"{source}_error"] = str(e)

        return results

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _get_domain(self, source: str, country: str, config: dict) -> str:
        if "domain" in config:
            return config["domain"]
        domains = config.get("domains", {})
        return domains.get(country.lower(), list(domains.values())[0] if domains else "")

    def _get_currency(self, source: str, country: str, config: dict) -> str:
        currencies = config.get("currencies", {})
        return currencies.get(country.lower(), config.get("currency_default", "USD"))

    def _is_product_url(self, url: str, domain: str, patterns: list[str]) -> bool:
        if domain not in url:
            return False
        if not patterns:
            return True
        return any(re.search(p, url) for p in patterns)

    def _clean_title(self, title: str, source: str) -> str:
        suffixes = [
            " | AliExpress", " - AliExpress",
            " | Amazon", " - Amazon", " : Amazon",
            " | Temu", " - Temu",
            " | Shopee", " - Shopee",
            " | MercadoLibre", " - MercadoLibre",
        ]
        for suffix in suffixes:
            title = title.replace(suffix, "")
        return title.strip()

    def _extract_price(self, item: dict) -> float:
        rich = item.get("rich_snippet", {})
        if isinstance(rich, dict):
            top = rich.get("top", {})
            if isinstance(top, dict):
                ext = top.get("detected_extensions", {})
                if isinstance(ext, dict):
                    price = ext.get("price", 0)
                    if price:
                        return float(price)

        snippet = item.get("snippet", "")
        # Intentar patrones de precio comunes
        patterns = [
            r"US\s?\$\s?([\d.,]+)",
            r"\$\s?([\d.,]+)",
            r"COP\s?([\d.,]+)",
            r"MXN\s?([\d.,]+)",
            r"R\$\s?([\d.,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    return float(price_str)
                except ValueError:
                    continue

        return 0.0

    def _extract_rating(self, item: dict) -> Optional[float]:
        rich = item.get("rich_snippet", {})
        if isinstance(rich, dict):
            top = rich.get("top", {})
            if isinstance(top, dict):
                ext = top.get("detected_extensions", {})
                if isinstance(ext, dict):
                    rating = ext.get("rating")
                    if rating:
                        try:
                            return float(rating)
                        except (ValueError, TypeError):
                            pass
        return None

    def _extract_reviews(self, item: dict) -> Optional[int]:
        rich = item.get("rich_snippet", {})
        if isinstance(rich, dict):
            top = rich.get("top", {})
            if isinstance(top, dict):
                ext = top.get("detected_extensions", {})
                if isinstance(ext, dict):
                    reviews = ext.get("reviews")
                    if reviews:
                        try:
                            return int(reviews)
                        except (ValueError, TypeError):
                            pass
        return None

    def _extract_seller(self, item: dict, source: str) -> str:
        snippet = item.get("snippet", "")
        if source == "amazon":
            match = re.search(r"(?:by|por)\s+([A-Za-z0-9\s]+?)(?:\s*[|·\-]|\s*$)", snippet)
            if match:
                return match.group(1).strip()
        if source == "aliexpress":
            displayed = item.get("displayed_link", "")
            if "aliexpress.com" in displayed:
                store_match = re.search(r"aliexpress\.com\s*›\s*store\s*›\s*(.+)", displayed)
                if store_match:
                    return store_match.group(1).strip()
        return ""


ecommerce_scraper = EcommerceScraperClient()