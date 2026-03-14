"""
Cliente async para SerpAPI — Google Shopping results.
Proporciona datos reales de precios y productos de Google Shopping.
"""

from __future__ import annotations

from typing import Optional

import httpx

from infra.config.database import settings


class SerpAPIClient:

    BASE_URL = "https://serpapi.com/search"

    def __init__(self) -> None:
        self._api_key = settings.SERPAPI_API_KEY

    async def search_google_shopping(
        self,
        query: str,
        country: str = "co",
        language: str = "es",
        num_results: int = 10,
    ) -> list[dict]:
        """
        Busca productos en Google Shopping vía SerpAPI.

        Args:
            query: Término de búsqueda
            country: Código de país (co, mx, ar, us)
            language: Idioma (es, en)
            num_results: Cantidad de resultados

        Returns:
            Lista de productos con datos de Google Shopping
        """
        if not self._api_key:
            return []

        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": country,
            "hl": language,
            "num": num_results,
            "api_key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for item in data.get("shopping_results", []):
            results.append({
                "source": "google_shopping",
                "name": item.get("title", ""),
                "price": self._parse_price(item.get("extracted_price", 0)),
                "currency": "USD" if country == "us" else "COP",
                "url": item.get("link", ""),
                "image_url": item.get("thumbnail", ""),
                "seller": item.get("source", ""),
                "rating": item.get("rating"),
                "reviews_count": item.get("reviews"),
                "delivery": item.get("delivery", ""),
            })

        return results

    async def search_google(
        self,
        query: str,
        country: str = "co",
        num_results: int = 5,
    ) -> list[dict]:
        """
        Búsqueda general en Google para obtener info de tendencias.
        """
        if not self._api_key:
            return []

        params = {
            "engine": "google",
            "q": query,
            "gl": country,
            "hl": "es",
            "num": num_results,
            "api_key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)

        if response.status_code != 200:
            return []

        data = response.json()
        results = []

        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "source": item.get("displayed_link", ""),
            })

        return results

    def _parse_price(self, price) -> float:
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.replace("$", "").replace(",", "").replace(".", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


serpapi_client = SerpAPIClient()