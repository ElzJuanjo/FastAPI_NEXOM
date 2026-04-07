"""
Cliente async para la API de Integraciones de Dropi.
Documentación: https://api.dropi.co/integrations/documentation

Auth: header dropi-integration-key en todas las requests.
El key se obtiene una vez desde el panel de Dropi y se guarda en .env

Nota: Dropi bloquea requests con User-Agent de librerías Python (httpx, python-requests).
Se usa requests con User-Agent custom ejecutado en asyncio.to_thread para compatibilidad async.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import requests as http

from infra.config.database import settings


class DropisError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Dropi error {status_code}: {detail}")


class DropisClient:

    BASE_URL = "https://api.dropi.co"
    TIMEOUT = 30
    HEADERS_BASE = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "PostmanRuntime/7.36.0",
    }

    def __init__(self) -> None:
        self._integration_key = settings.DROPI_INTEGRATION_KEY

    def _headers(self) -> dict:
        return {
            **self.HEADERS_BASE,
            "dropi-integration-key": self._integration_key,
        }

    def _ensure_key(self) -> None:
        if not self._integration_key:
            raise DropisError(401, "DROPI_INTEGRATION_KEY no configurado en .env")

    # ---------------------------------------------------------------------------
    # Request helpers (sync, ejecutados en thread)
    # ---------------------------------------------------------------------------

    def _post(self, path: str, payload: dict | None = None) -> dict:
        resp = http.post(
            f"{self.BASE_URL}{path}",
            json=payload or {},
            headers=self._headers(),
            timeout=self.TIMEOUT,
        )
        if resp.status_code not in (200, 201):
            raise DropisError(resp.status_code, resp.text)
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = http.get(
            f"{self.BASE_URL}{path}",
            params=params,
            headers=self._headers(),
            timeout=self.TIMEOUT,
        )
        if resp.status_code != 200:
            raise DropisError(resp.status_code, resp.text)
        return resp.json()

    # ---------------------------------------------------------------------------
    # Productos
    # ---------------------------------------------------------------------------

    async def search_products(
        self,
        query: str = "",
        category: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> list[dict]:
        """
        Busca productos en el catálogo de Dropi.
        La API no soporta búsqueda por texto, así que traemos un lote
        y filtramos localmente por nombre/categoría.
        """
        self._ensure_key()

        fetch_size = limit * 5 if query else limit
        payload = {"pageSize": min(fetch_size, 100)}

        data = await asyncio.to_thread(self._post, "/integrations/products/index", payload)
        products_raw = data.get("objects", [])

        results = [self._normalize_product(p) for p in products_raw if isinstance(products_raw, list)]

        if query:
            q = query.lower()
            words = q.split()
            filtered = [
                p for p in results
                if any(
                    word in p["name"].lower()
                    or word in p.get("category", "").lower()
                    for word in words
                )
            ]
            results = filtered if filtered else results

        return results[:limit]

    async def get_product(self, product_id: int) -> Optional[dict]:
        """Obtiene detalles de un producto por ID."""
        self._ensure_key()
        try:
            data = await asyncio.to_thread(self._get, f"/integrations/products/v2/{product_id}")
            return self._normalize_product(data) if data else None
        except DropisError:
            return None

    async def get_product_stock(self, product_id: int) -> Optional[dict]:
        """Consulta stock de un producto."""
        product = await self.get_product(product_id)
        if product:
            return {
                "product_id": product_id,
                "stock": product.get("stock", 0),
                "variations": product.get("variations", []),
            }
        return None

    # ---------------------------------------------------------------------------
    # Órdenes
    # ---------------------------------------------------------------------------

    async def create_order(self, order_data: dict) -> dict:
        """Crea una orden en Dropi."""
        self._ensure_key()
        return await asyncio.to_thread(self._post, "/integrations/orders/myorders", order_data)

    async def get_order(self, order_id: int) -> Optional[dict]:
        """Consulta estado de una orden."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, f"/integrations/orders/myorders/{order_id}")
        except DropisError:
            return None

    async def list_orders(self, page: int = 1, per_page: int = 20, status: str = "") -> dict:
        """Lista órdenes del usuario."""
        self._ensure_key()
        params = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        return await asyncio.to_thread(self._get, "/integrations/orders/myorders", params)

    async def get_order_by_guide(self, guide: str) -> Optional[dict]:
        """Busca orden por número de guía."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, f"/integrations/orders/myorderbyguide/{guide}")
        except DropisError:
            return None

    # ---------------------------------------------------------------------------
    # Ciudades, Transportadoras, Cotización
    # ---------------------------------------------------------------------------

    async def list_departments_with_cities(self) -> list[dict]:
        """Lista departamentos con sus ciudades."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/department/all/with-cities")
        except DropisError:
            return []

    async def get_shipping_quote(self, city_id: int, weight_gr: int) -> Optional[dict]:
        """Cotiza envío a una ciudad."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(
                self._post,
                "/integrations/orders/cotizaEnvioTransportadoraV2",
                {"city_id": city_id, "weight": weight_gr},
            )
        except DropisError:
            return None

    async def check_coverage(self, city_id: int) -> Optional[dict]:
        """Verifica cobertura de envío en una ciudad."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/city/coverage/v2", {"city_id": city_id})
        except DropisError:
            return None

    async def list_categories(self) -> list[dict]:
        """Lista categorías disponibles."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/categories")
        except DropisError:
            return []

    async def list_carriers(self) -> list[dict]:
        """Lista transportadoras disponibles."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/distribution_companies")
        except DropisError:
            return []

    async def whoami(self) -> Optional[dict]:
        """Obtiene información del usuario autenticado."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._post, "/integrations/whoiam")
        except DropisError:
            return None

    # ---------------------------------------------------------------------------
    # Bodegas
    # ---------------------------------------------------------------------------

    async def list_warehouses(self) -> list[dict]:
        """Lista bodegas del usuario."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/users/warehouses/index")
        except DropisError:
            return []

    # ---------------------------------------------------------------------------
    # Pick ups
    # ---------------------------------------------------------------------------

    async def list_pickups(self) -> list[dict]:
        """Lista pick ups programados."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/pick_ups")
        except DropisError:
            return []

    async def create_pickup(self, pickup_data: dict) -> dict:
        """Crea un pick up."""
        self._ensure_key()
        return await asyncio.to_thread(self._post, "/integrations/pick_ups", pickup_data)

    # ---------------------------------------------------------------------------
    # Shop info
    # ---------------------------------------------------------------------------

    async def get_shop_data(self) -> Optional[dict]:
        """Obtiene información de la tienda autenticada."""
        self._ensure_key()
        try:
            return await asyncio.to_thread(self._get, "/integrations/shops/get/shop-data")
        except DropisError:
            return None

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _normalize_product(self, p: dict) -> dict:
        """Normaliza un producto de Dropi al formato interno de NEXOM."""
        total_stock = 0
        warehouses = p.get("warehouse_product", [])
        if warehouses:
            total_stock = sum(w.get("stock", 0) for w in warehouses)

        variations = p.get("variations", [])
        if variations and total_stock == 0:
            total_stock = sum(v.get("stock", 0) for v in variations)

        categories = p.get("categories", [])
        category_name = categories[0].get("name", "") if categories else ""

        user = p.get("user", {})
        supplier_name = user.get("store_name", user.get("name", ""))

        gallery = p.get("gallery", [])
        image_url = ""
        if gallery:
            img = gallery[0]
            image_url = img.get("url") or img.get("urlS3", "")
            if image_url and not image_url.startswith("http"):
                image_url = f"https://dropi.co/storage/{image_url}"

        normalized_variations = []
        for v in variations:
            attrs = v.get("attribute_values", [])
            attr_label = ", ".join(a.get("value", "") for a in attrs) if attrs else ""
            normalized_variations.append({
                "id": v.get("id"),
                "name": attr_label,
                "price": float(v.get("sale_price", 0) or 0),
                "suggested_price": float(v.get("suggested_price", 0) or 0),
                "stock": v.get("stock", 0),
                "sku": v.get("sku", ""),
            })

        return {
            "id": p.get("id"),
            "name": p.get("name", ""),
            "type": p.get("type", "SIMPLE"),
            "price": float(p.get("sale_price", 0) or 0),
            "suggested_price": float(p.get("suggested_price", 0) or 0),
            "currency": "COP",
            "category": category_name,
            "stock": total_stock,
            "image_url": image_url,
            "supplier": supplier_name,
            "sku": p.get("sku", ""),
            "variations": normalized_variations,
        }


dropi_client = DropisClient()