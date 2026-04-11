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
            if not data:
                return None

            # La API v2 puede devolver el producto envuelto en diferentes keys
            product_data = data
            if "name" not in data and "sale_price" not in data:
                for key in ("objects", "data", "product", "result"):
                    candidate = data.get(key)
                    if isinstance(candidate, dict):
                        product_data = candidate
                        break
                    elif isinstance(candidate, list) and candidate:
                        product_data = candidate[0]
                        break

            return self._normalize_product(product_data)
        except DropisError:
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Dropi get_product({product_id}) error: {e}")
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
        import logging
        logger = logging.getLogger(__name__)

        # Debug: log the keys we receive to diagnose mapping issues
        logger.info(f"Dropi _normalize_product keys: {list(p.keys())[:20]}")

        # Temporary debug: log raw structure of photos and first variation
        raw_photos = p.get("photos") or p.get("gallery") or []
        logger.info(f"Dropi raw photos type={type(raw_photos).__name__}, len={len(raw_photos) if isinstance(raw_photos, list) else 'N/A'}, sample={str(raw_photos[:1])[:500] if isinstance(raw_photos, list) and raw_photos else str(raw_photos)[:500]}")

        raw_variations = p.get("variations") or []
        if isinstance(raw_variations, list) and raw_variations:
            logger.info(f"Dropi raw variation[0] keys={list(raw_variations[0].keys()) if isinstance(raw_variations[0], dict) else 'not-dict'}, sample={str(raw_variations[0])[:500]}")

        raw_wh = p.get("warehouse_product") or []
        logger.info(f"Dropi raw warehouse_product type={type(raw_wh).__name__}, len={len(raw_wh) if isinstance(raw_wh, list) else 'N/A'}, sample={str(raw_wh[:1])[:500] if isinstance(raw_wh, list) and raw_wh else str(raw_wh)[:500]}")

        # Name: try multiple possible field names
        name = (
            p.get("name")
            or p.get("title")
            or p.get("product_name")
            or ""
        )

        # Stock from warehouses
        total_stock = 0
        warehouses = p.get("warehouse_product") or p.get("warehouses") or []
        if isinstance(warehouses, list):
            total_stock = sum(w.get("stock", 0) for w in warehouses if isinstance(w, dict))

        # Variations — stock lives inside warehouse_product_variation per variation
        variations = p.get("variations") or []
        if isinstance(variations, list):
            for v in variations:
                if not isinstance(v, dict):
                    continue
                # Direct stock on variation
                var_stock_direct = v.get("stock", 0) or 0
                # Stock from warehouse_product_variation (array of warehouse entries)
                wpv = v.get("warehouse_product_variation") or []
                if isinstance(wpv, list):
                    wpv_stock = sum(w.get("stock", 0) or 0 for w in wpv if isinstance(w, dict))
                    var_stock_direct = max(var_stock_direct, wpv_stock)
                elif isinstance(wpv, dict):
                    var_stock_direct = max(var_stock_direct, wpv.get("stock", 0) or 0)
                total_stock += var_stock_direct

        # Categories
        categories = p.get("categories") or []
        category_name = ""
        if isinstance(categories, list) and categories:
            first_cat = categories[0]
            if isinstance(first_cat, dict):
                category_name = first_cat.get("name", "")
            elif isinstance(first_cat, str):
                category_name = first_cat

        # Supplier
        user = p.get("user") or {}
        if isinstance(user, dict):
            supplier_name = user.get("store_name") or user.get("name") or ""
        else:
            supplier_name = ""

        # Image from photos/gallery
        gallery = p.get("photos") or p.get("gallery") or p.get("images") or []
        image_url = ""
        if isinstance(gallery, list) and gallery:
            # Find the main photo first, fallback to first
            main_photo = next((img for img in gallery if isinstance(img, dict) and img.get("main")), None)
            img = main_photo or gallery[0]
            if isinstance(img, dict):
                # Prefer urlS3 (CDN hosted), then url (legacy path)
                raw_url = img.get("urlS3") or img.get("url") or img.get("src") or ""
            elif isinstance(img, str):
                raw_url = img
            else:
                raw_url = ""
            # Build full URL if relative
            if raw_url and not raw_url.startswith("http"):
                image_url = f"https://dropi.co/storage/{raw_url}"
            else:
                image_url = raw_url
                
        # Fallback: direct image fields
        if not image_url:
            image_url = p.get("image_url") or p.get("image") or p.get("thumbnail") or ""

        # Price
        price = float(p.get("sale_price") or p.get("price") or 0)
        suggested_price = float(p.get("suggested_price") or p.get("retail_price") or price or 0)

        # Variations normalization
        normalized_variations = []
        for v in (variations if isinstance(variations, list) else []):
            if not isinstance(v, dict):
                continue
            attrs = v.get("attribute_values") or v.get("attributes") or []
            attr_label = ""
            if isinstance(attrs, list):
                attr_parts = []
                for a in attrs:
                    if isinstance(a, dict):
                        # Include attribute name if available (e.g., "Tallas Dama: 39")
                        attr_obj = a.get("attribute") or {}
                        attr_name = attr_obj.get("name", "") if isinstance(attr_obj, dict) else ""
                        val = a.get("value", "")
                        attr_parts.append(f"{attr_name}: {val}" if attr_name else val)
                    else:
                        attr_parts.append(str(a))
                attr_label = ", ".join(attr_parts)
            elif isinstance(attrs, str):
                attr_label = attrs

            if not attr_label:
                attr_label = v.get("description") or v.get("name") or ""

            # Stock from warehouse_product_variation
            var_stock = 0
            wpv = v.get("warehouse_product_variation") or []
            if isinstance(wpv, list):
                var_stock = sum(w.get("stock", 0) or 0 for w in wpv if isinstance(w, dict))
            elif isinstance(wpv, dict):
                var_stock = wpv.get("stock", 0) or 0
            if not var_stock:
                var_stock = v.get("stock", 0) or 0

            normalized_variations.append({
                "id": v.get("id"),
                "name": attr_label,
                "price": float(v.get("sale_price") or v.get("price") or 0),
                "suggested_price": float(v.get("suggested_price") or 0),
                "stock": var_stock,
                "sku": v.get("sku") or "",
            })

        result = {
            "id": p.get("id"),
            "name": name,
            "description": p.get("description") or p.get("dropi_app_description") or "",
            "type": p.get("type", "SIMPLE"),
            "price": price,
            "suggested_price": suggested_price,
            "currency": "COP",
            "category": category_name,
            "stock": total_stock,
            "image_url": image_url,
            "supplier": supplier_name,
            "sku": p.get("sku") or "",
            "variations": normalized_variations,
        }

        logger.info(f"Dropi normalized: name='{name}', price={price}, stock={total_stock}, image={'yes' if image_url else 'no'}, variations={len(normalized_variations)}")

        return result


dropi_client = DropisClient()