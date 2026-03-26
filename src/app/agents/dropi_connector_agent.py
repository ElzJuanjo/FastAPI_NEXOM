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
from app.agents.dropi_filters import evaluate_products


class DropiConnectorAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "dropi_connector"

    @property
    def default_model(self) -> str:
        return "openai/gpt-5.4-nano"

    @property
    def system_prompt(self) -> str:
        return """You are an expert assistant for the Dropi platform (dropshipping in Colombia/Latin America).
You are provided REAL data from the Dropi catalog.

Your job is:
1. Present Dropi products clearly and attractively
2. Calculate margins: Dropi price (cost) vs suggested price (retail)
3. Report stock availability and variations
4. Assist in order preparation
5. Quote shipping when city data is provided
6. Evaluate suppliers by quality and delivery time

AUTOMATIC FILTER PARAMETERS:
- Minimum acceptable margin: 35%
- Maximum delivery time: 15 days
- Minimum supplier rating: ≥4.0
- Products that don't meet criteria → mark with ⚠️ and explain why

For each product show:
- Name and description
- Dropi price (your cost) and suggested price (retail)
- Profit margin (in local currency and %)
- Available stock by warehouse/variation
- Supplier (store name)
- Estimated delivery time
- ⚠️ Alerts if low stock (<50 units) or insufficient margin

Respond in the same language the user writes in. Be direct and action-oriented.

CRITICAL INTERACTION RULES:
- NEVER offer numbered option menus. Present all found products directly with their data.
- If the user wants to sync or order, ask for the specific required data in one message.
- EXECUTE, DON'T ASK. Every message without deliverable content is wasted money."""

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
            approved = [p for p in products if p.get("passes_filters", True)]
            rejected = [p for p in products if not p.get("passes_filters", True)]

            parts.append(f"=== PRODUCTOS DE DROPI ({len(products)} encontrados, {len(approved)} aprobados) ===\n")

            for i, p in enumerate(products, 1):
                margin_pct = p.get("margin_pct", 0)
                margin_cop = p.get("margin_cop", 0)
                status_icon = "✅" if p.get("passes_filters", True) else "⚠️"

                parts.append(
                    f"{i}. {status_icon} {p['name']}\n"
                    f"   Precio Dropi (costo): COP {p.get('price', 0):,.0f}\n"
                    f"   Precio sugerido (venta): COP {p.get('suggested_price', 0):,.0f}\n"
                    f"   Margen: COP {margin_cop:,.0f} ({margin_pct:.0f}%)\n"
                    f"   Stock: {p.get('stock', 'N/A')}\n"
                    f"   Categoría: {p.get('category', 'N/A')}\n"
                    f"   Proveedor: {p.get('supplier', 'N/A')}\n"
                    f"   Quality Score: {p.get('quality_score', 0)}/100"
                )

                alerts = p.get("alerts", [])
                if alerts:
                    parts.append(f"   Alertas: {' | '.join(alerts)}")

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

        return self._build_messages_with_history("\n".join(parts), context)

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 16384,
    ) -> dict:
        context = context or {}
        dropi_data = {}

        # Búsqueda de productos
        try:
            products = await dropi_client.search_products(query=user_input, limit=10)
            products = evaluate_products(products)
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
            "products_approved": len([p for p in dropi_data.get("products", []) if p.get("passes_filters", False)]),
        }

        return result