"""
Agente conectado a Dropi.
Usa el cliente de Dropi para buscar productos, consultar stock,
y asistir en la creación de órdenes. El LLM interpreta la solicitud
y presenta los resultados de forma amigable.
"""

from __future__ import annotations

import json

from .base_agent import BaseAgent
from infra.tools.dropi_client import dropi_client


class DropiConnectorAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "dropi_connector"

    @property
    def default_model(self) -> str:
        return "openai/gpt-4o"

    @property
    def system_prompt(self) -> str:
        return """Eres un asistente experto en la plataforma Dropi (dropshipping en Colombia/LatAm).
Se te proporcionan datos REALES del catálogo de Dropi.

Tu trabajo es:
1. Presentar productos de Dropi de forma clara y atractiva.
2. Calcular márgenes: precio Dropi (costo) vs precio sugerido (venta).
3. Informar sobre disponibilidad de stock y variaciones.
4. Asistir en la preparación de órdenes.
5. Cotizar envíos cuando se proporcionen datos de ciudades.

Para cada producto muestra:
- Nombre y descripción
- Precio Dropi (tu costo) y Precio sugerido (venta)
- Margen de ganancia (en COP y %)
- Stock disponible
- Variaciones disponibles (tallas, colores, etc.)
- Proveedor

Si el usuario quiere crear una orden, solicita:
- Producto(s) y cantidad
- Nombre del cliente
- Teléfono
- Ciudad de destino
- Dirección completa

Responde siempre en español. Sé directo y orientado a la acción."""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        dropi_data = context.get("_dropi_data", {}) if context else {}

        parts = [f"Solicitud del usuario: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in user_context.items())
                parts.append(f"Contexto:\n{context_str}\n")

        products = dropi_data.get("products", [])
        if products:
            parts.append(f"=== PRODUCTOS DE DROPI ({len(products)} encontrados) ===")
            for i, p in enumerate(products, 1):
                margin = p.get("suggested_price", 0) - p.get("price", 0)
                margin_pct = (margin / p["price"] * 100) if p.get("price") else 0
                parts.append(
                    f"{i}. {p['name']}\n"
                    f"   Descripción: {p.get('description', 'N/A')}\n"
                    f"   Precio Dropi (costo): COP {p.get('price', 0):,.0f}\n"
                    f"   Precio sugerido (venta): COP {p.get('suggested_price', 0):,.0f}\n"
                    f"   Margen: COP {margin:,.0f} ({margin_pct:.0f}%)\n"
                    f"   Stock: {p.get('stock', 'N/A')}\n"
                    f"   Categoría: {p.get('category', 'N/A')}\n"
                    f"   Proveedor: {p.get('supplier', 'N/A')}"
                )
                variations = p.get("variations", [])
                if variations:
                    var_str = ", ".join(f"{v['name']} (stock: {v.get('stock', 'N/A')})" for v in variations)
                    parts.append(f"   Variaciones: {var_str}")

        stock_info = dropi_data.get("stock_info")
        if stock_info:
            parts.append(f"\n=== STOCK EN TIEMPO REAL ===\n{json.dumps(stock_info, indent=2, ensure_ascii=False)}")

        shipping_info = dropi_data.get("shipping_quote")
        if shipping_info:
            parts.append(f"\n=== COTIZACIÓN DE ENVÍO ===\n{json.dumps(shipping_info, indent=2, ensure_ascii=False)}")

        order_result = dropi_data.get("order_result")
        if order_result:
            parts.append(f"\n=== RESULTADO DE ORDEN ===\n{json.dumps(order_result, indent=2, ensure_ascii=False)}")

        if not products and not stock_info and not shipping_info and not order_result:
            parts.append("No se encontraron datos de Dropi para esta consulta. Responde con información general sobre Dropi.")

        return [{"role": "user", "content": "\n".join(parts)}]

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> dict:
        context = context or {}
        dropi_data = {}

        # Detectar intención y ejecutar acciones en Dropi
        input_lower = user_input.lower()

        # Búsqueda de productos
        try:
            products = await dropi_client.search_products(query=user_input, limit=10)
            dropi_data["products"] = products
        except Exception as e:
            dropi_data["products_error"] = str(e)

        # Si piden stock de un producto específico
        product_id = context.get("product_id")
        if product_id:
            try:
                stock = await dropi_client.get_product_stock(int(product_id))
                dropi_data["stock_info"] = stock
            except Exception as e:
                dropi_data["stock_error"] = str(e)

        # Si piden cotización de envío
        city_id = context.get("city_id")
        if city_id:
            weight = context.get("weight_gr", 500)
            try:
                quote = await dropi_client.get_shipping_quote(int(city_id), int(weight))
                dropi_data["shipping_quote"] = quote
            except Exception as e:
                dropi_data["shipping_error"] = str(e)

        # Inyectar datos en contexto
        enriched_context = {**context, "_dropi_data": dropi_data}

        # Ejecutar LLM
        messages = self.build_messages(user_input, enriched_context)
        model = model_override or self.default_model

        result = await self._client.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=self.system_prompt,
        )

        result["dropi_data"] = {
            "products_found": len(dropi_data.get("products", [])),
        }

        return result