"""
Cliente async para la API de Dropi.
Basado en la documentación oficial:
- Auth via login (email/password) → token
- Endpoints: productos, órdenes, ciudades, transportadoras, guías
- Modo mock disponible cuando no hay credenciales
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from infra.config.database import settings


# ---------------------------------------------------------------------------
# Mock data — datos realistas de Dropi para desarrollo sin credenciales
# ---------------------------------------------------------------------------

MOCK_PRODUCTS = [
    {
        "id": 100001,
        "name": "Serum Vitamina C 30ml - Cuidado Facial",
        "description": "Serum facial con vitamina C pura al 20%. Hidrata, ilumina y protege la piel.",
        "price": 25000,
        "suggested_price": 55000,
        "currency": "COP",
        "category": "Salud y Belleza",
        "stock": 350,
        "image_url": "https://via.placeholder.com/300x300?text=Serum+VitC",
        "supplier": "BellezaPro CO",
        "weight_gr": 120,
        "variations": [
            {"id": 1001, "name": "30ml", "price": 25000, "stock": 200},
            {"id": 1002, "name": "50ml", "price": 38000, "stock": 150},
        ],
    },
    {
        "id": 100002,
        "name": "Audífonos Bluetooth TWS i12 - Negro",
        "description": "Audífonos inalámbricos Bluetooth 5.0. Estuche de carga incluido.",
        "price": 12000,
        "suggested_price": 35000,
        "currency": "COP",
        "category": "Tecnología",
        "stock": 1200,
        "image_url": "https://via.placeholder.com/300x300?text=TWS+i12",
        "supplier": "TechImport SAS",
        "weight_gr": 85,
        "variations": [
            {"id": 2001, "name": "Negro", "price": 12000, "stock": 600},
            {"id": 2002, "name": "Blanco", "price": 12000, "stock": 600},
        ],
    },
    {
        "id": 100003,
        "name": "Faja Reductora Colombiana - Cintura Avispa",
        "description": "Faja reductora de alta compresión. Uso diario o post-parto.",
        "price": 18000,
        "suggested_price": 49900,
        "currency": "COP",
        "category": "Moda y Accesorios",
        "stock": 800,
        "image_url": "https://via.placeholder.com/300x300?text=Faja+Reductora",
        "supplier": "ModaFit CO",
        "weight_gr": 250,
        "variations": [
            {"id": 3001, "name": "S", "price": 18000, "stock": 200},
            {"id": 3002, "name": "M", "price": 18000, "stock": 300},
            {"id": 3003, "name": "L", "price": 18000, "stock": 200},
            {"id": 3004, "name": "XL", "price": 18000, "stock": 100},
        ],
    },
    {
        "id": 100004,
        "name": "Lámpara LED Sunset Projection",
        "description": "Lámpara decorativa efecto atardecer. USB recargable. 16 colores.",
        "price": 15000,
        "suggested_price": 42000,
        "currency": "COP",
        "category": "Hogar y Decoración",
        "stock": 450,
        "image_url": "https://via.placeholder.com/300x300?text=Lamp+Sunset",
        "supplier": "HomeTrend CO",
        "weight_gr": 320,
        "variations": [],
    },
    {
        "id": 100005,
        "name": "Banda Elástica de Resistencia Set x5",
        "description": "Set de 5 bandas de resistencia para ejercicio. Diferentes niveles.",
        "price": 8000,
        "suggested_price": 25000,
        "currency": "COP",
        "category": "Deportes y Bienestar",
        "stock": 2000,
        "image_url": "https://via.placeholder.com/300x300?text=Bandas+Fitness",
        "supplier": "FitGear CO",
        "weight_gr": 180,
        "variations": [],
    },
]

MOCK_CITIES = [
    {"id": 1, "name": "Bogotá", "department": "Cundinamarca"},
    {"id": 2, "name": "Medellín", "department": "Antioquia"},
    {"id": 3, "name": "Cali", "department": "Valle del Cauca"},
    {"id": 4, "name": "Barranquilla", "department": "Atlántico"},
    {"id": 5, "name": "Cartagena", "department": "Bolívar"},
    {"id": 6, "name": "Bucaramanga", "department": "Santander"},
]


class DropisError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Dropi error {status_code}: {detail}")


class DropisClient:

    def __init__(self) -> None:
        self._base_url = settings.DROPI_API_BASE_URL.rstrip("/")
        self._email = settings.DROPI_EMAIL
        self._password = settings.DROPI_PASSWORD
        self._use_mock = settings.DROPI_USE_MOCK
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    # ---------------------------------------------------------------------------
    # Auth
    # ---------------------------------------------------------------------------

    async def _ensure_auth(self) -> None:
        """Obtiene o refresca el token de autenticación."""
        if self._use_mock:
            return

        if self._token and time.time() < self._token_expiry:
            return

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/login/sign-in",
                json={"email": self._email, "password": self._password},
            )

        if response.status_code != 200:
            raise DropisError(response.status_code, "Login fallido en Dropi")

        data = response.json()
        self._token = data.get("token") or data.get("access_token")
        # Token válido por 23 horas (refresh antes de 24h)
        self._token_expiry = time.time() + (23 * 3600)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

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
        """Busca productos en el catálogo de Dropi."""
        if self._use_mock:
            return self._mock_search(query, category, limit)

        await self._ensure_auth()

        params = {"page": page, "limit": limit}
        if query:
            params["search"] = query
        if category:
            params["category"] = category

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/products/public",
                params=params,
                headers=self._headers(),
            )

        if response.status_code != 200:
            raise DropisError(response.status_code, response.text)

        data = response.json()
        return data.get("data", data.get("products", []))

    async def get_product(self, product_id: int) -> Optional[dict]:
        """Obtiene detalles de un producto por ID."""
        if self._use_mock:
            return next((p for p in MOCK_PRODUCTS if p["id"] == product_id), None)

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/products/{product_id}",
                headers=self._headers(),
            )

        if response.status_code != 200:
            return None

        return response.json()

    async def get_product_stock(self, product_id: int) -> Optional[dict]:
        """Consulta stock en tiempo real."""
        if self._use_mock:
            product = next((p for p in MOCK_PRODUCTS if p["id"] == product_id), None)
            if product:
                return {"product_id": product_id, "stock": product["stock"], "variations": product.get("variations", [])}
            return None

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/products/{product_id}/stock",
                headers=self._headers(),
            )

        if response.status_code != 200:
            return None

        return response.json()

    # ---------------------------------------------------------------------------
    # Órdenes
    # ---------------------------------------------------------------------------

    async def create_order(self, order_data: dict) -> dict:
        """
        Crea una orden en Dropi.
        order_data debe contener: customer_name, customer_phone, city_id,
        address, products[{id, price, quantity, variation_id?}], total
        """
        if self._use_mock:
            return {
                "id": 999001,
                "status": "created",
                "tracking_number": "MOCK-TRK-001",
                "message": "Orden mock creada exitosamente",
                **order_data,
            }

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/orders/create",
                json=order_data,
                headers=self._headers(),
            )

        if response.status_code not in (200, 201):
            raise DropisError(response.status_code, response.text)

        return response.json()

    async def get_order(self, order_id: int) -> Optional[dict]:
        """Consulta estado de una orden."""
        if self._use_mock:
            return {
                "id": order_id,
                "status": "processing",
                "tracking_number": "MOCK-TRK-001",
                "shipping_status": "en_bodega",
            }

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/orders/{order_id}",
                headers=self._headers(),
            )

        if response.status_code != 200:
            return None

        return response.json()

    # ---------------------------------------------------------------------------
    # Ciudades y Transportadoras
    # ---------------------------------------------------------------------------

    async def list_cities(self) -> list[dict]:
        """Lista ciudades disponibles para envío."""
        if self._use_mock:
            return MOCK_CITIES

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/cities",
                headers=self._headers(),
            )

        if response.status_code != 200:
            return []

        return response.json()

    async def get_shipping_quote(self, city_id: int, weight_gr: int) -> Optional[dict]:
        """Cotiza envío a una ciudad."""
        if self._use_mock:
            city = next((c for c in MOCK_CITIES if c["id"] == city_id), None)
            base_cost = 8000 if city and city["name"] == "Bogotá" else 12000
            return {
                "city_id": city_id,
                "city_name": city["name"] if city else "Desconocida",
                "shipping_cost": base_cost + (weight_gr // 1000) * 2000,
                "estimated_days": 2 if city and city["name"] == "Bogotá" else 4,
            }

        await self._ensure_auth()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/shipping/quote",
                json={"city_id": city_id, "weight": weight_gr},
                headers=self._headers(),
            )

        if response.status_code != 200:
            return None

        return response.json()

    # ---------------------------------------------------------------------------
    # Mock helpers
    # ---------------------------------------------------------------------------

    def _mock_search(self, query: str, category: str, limit: int) -> list[dict]:
            results = MOCK_PRODUCTS

            if query:
                q = query.lower()
                # Buscar en nombre, descripción y categoría
                results = [
                    p for p in results
                    if q in p["name"].lower()
                    or q in p.get("description", "").lower()
                    or q in p.get("category", "").lower()
                    or any(word in p["name"].lower() or word in p.get("description", "").lower() or word in p.get("category", "").lower() for word in q.split())
                ]

            if category:
                cat = category.lower()
                results = [p for p in results if cat in p.get("category", "").lower()]

            # Si no hay match, devolver todo el catálogo
            if not results:
                results = MOCK_PRODUCTS

            return results[:limit]


dropi_client = DropisClient()