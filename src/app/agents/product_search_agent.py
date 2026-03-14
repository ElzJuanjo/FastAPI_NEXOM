"""
Agente de Búsqueda de Productos — versión con datos reales.
Flujo: Scraping (MercadoLibre + Google Shopping) → LLM (análisis) → Response estructurado.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .base_agent import BaseAgent
from infra.tools.mercadolibre_client import mercadolibre_client
from infra.tools.serpapi_client import serpapi_client
from infra.tools.ecommerce_scraper import ecommerce_scraper


class ProductSearchAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "product_search"

    @property
    def default_model(self) -> str:
        return "openai/gpt-4o"

    @property
    def system_prompt(self) -> str:
        return """Eres un analista experto en E-Commerce para Latinoamérica. 
Se te proporcionan datos REALES de productos obtenidos de múltiples fuentes:
- MercadoLibre (precios de mercado local)
- Google Shopping (precios retail y comparativa)
- AliExpress (precios de proveedor/mayorista)
- Amazon (precios retail internacionales, reviews)
- Temu (precios bajos, tendencias)
- Shopee (mercado LatAm emergente)

Tu trabajo es:
1. Analizar los datos reales proporcionados (NO inventar precios ni productos).
2. Comparar precios entre fuentes (especialmente proveedor vs retail).
3. Calcular márgenes reales: precio mayorista (AliExpress/Temu) vs precio retail (ML/Amazon).
4. Evaluar el nivel de competencia según cantidad de vendedores y reviews.
5. Identificar oportunidades de arbitraje entre plataformas.
6. Dar recomendaciones accionables.

REGLAS CRÍTICAS:
- SOLO usa los datos proporcionados, NO inventes productos ni precios.
- Siempre cita la fuente.
- Compara precios entre proveedor (AliExpress/Temu) y retail (ML/Amazon/Google Shopping).
- Si no hay suficientes datos de alguna fuente, indícalo claramente.
- Responde en español.

Formato de respuesta:
1. TABLA COMPARATIVA: Producto | Precio Proveedor | Precio Retail | Margen | Fuentes
2. TOP 3 OPORTUNIDADES: Las mejores oportunidades con justificación
3. ANÁLISIS DE COMPETENCIA: Nivel de saturación por producto
4. RECOMENDACIONES: Acciones concretas para el usuario
5. ALERTAS: Productos a evitar y por qué"""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        """Override: incluye los datos scrapeados en el mensaje."""
        scraped_data = context.get("_scraped_data", {}) if context else {}
        timestamp = context.get("_scraped_at", "") if context else ""

        # Construir contexto con datos reales
        parts = [f"Consulta del usuario: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in user_context.items())
                parts.append(f"Contexto adicional:\n{context_str}\n")

        if scraped_data:
            parts.append(f"Fecha de consulta: {timestamp}\n")

            ml_data = scraped_data.get("mercadolibre", [])
            if ml_data:
                parts.append(f"=== DATOS DE MERCADOLIBRE ({len(ml_data)} productos) ===")
                for i, p in enumerate(ml_data[:15], 1):
                    parts.append(
                        f"{i}. {p['name']}\n"
                        f"   Precio: {p['currency']} {p['price']:,.0f}\n"
                        f"   Vendidos: {p.get('sold_quantity', 'N/A')}\n"
                        f"   Vendedor: {p.get('seller', 'N/A')}\n"
                        f"   Envío gratis: {'Sí' if p.get('free_shipping') else 'No'}\n"
                        f"   URL: {p.get('url', '')}"
                    )

            gs_data = scraped_data.get("google_shopping", [])
            if gs_data:
                parts.append(f"\n=== DATOS DE GOOGLE SHOPPING ({len(gs_data)} productos) ===")
                for i, p in enumerate(gs_data[:10], 1):
                    parts.append(
                        f"{i}. {p['name']}\n"
                        f"   Precio: {p.get('currency', '')} {p['price']:,.0f}\n"
                        f"   Vendedor: {p.get('seller', 'N/A')}\n"
                        f"   Rating: {p.get('rating', 'N/A')}\n"
                        f"   Reviews: {p.get('reviews_count', 'N/A')}\n"
                        f"   URL: {p.get('url', '')}"
                    )
                    
            # Fuentes adicionales
            for source_key in ["aliexpress", "amazon", "temu", "shopee"]:
                source_data = scraped_data.get(source_key, [])
                if source_data:
                    source_label = source_key.upper().replace("_", " ")
                    parts.append(f"\n=== DATOS DE {source_label} ({len(source_data)} productos) ===")
                    for i, p in enumerate(source_data[:8], 1):
                        line = (
                            f"{i}. {p['name']}\n"
                            f"   Precio: {p.get('currency', 'USD')} {p['price']:,.2f}\n"
                        )
                        if p.get('rating'):
                            line += f"   Rating: {p['rating']}\n"
                        if p.get('reviews_count'):
                            line += f"   Reviews: {p['reviews_count']}\n"
                        if p.get('seller'):
                            line += f"   Vendedor: {p['seller']}\n"
                        line += f"   URL: {p.get('url', '')}"
                        parts.append(line)                
                
        else:
            parts.append(
                "NOTA: No se pudieron obtener datos de scraping. "
                "Responde con tu conocimiento pero indica claramente que los datos NO están verificados en tiempo real."
            )

        return [{"role": "user", "content": "\n".join(parts)}]

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Override: primero scrapea, luego analiza con LLM.
        """
        context = context or {}
        country = context.get("country", context.get("market", "colombia")).lower()

        # 1. Scraping real
        scraped_data = {}

        # MercadoLibre (siempre disponible, sin API key)
        try:
            ml_results = await mercadolibre_client.search_products(
                query=user_input,
                country=country,
                limit=15,
                sort="relevance",
            )
            scraped_data["mercadolibre"] = ml_results
        except Exception as e:
            scraped_data["mercadolibre"] = []
            scraped_data["mercadolibre_error"] = str(e)

        # Google Shopping (requiere SerpAPI key)
        try:
            country_code = {
                "colombia": "co", "mexico": "mx", "argentina": "ar",
                "chile": "cl", "peru": "pe", "brasil": "br",
            }.get(country, "co")

            gs_results = await serpapi_client.search_google_shopping(
                query=user_input,
                country=country_code,
                num_results=10,
            )
            scraped_data["google_shopping"] = gs_results
        except Exception as e:
            scraped_data["google_shopping"] = []
            scraped_data["google_shopping_error"] = str(e)
            
        # AliExpress, Amazon, Temu, Shopee
        try:
            extra_results = await ecommerce_scraper.search_all(
                query=user_input,
                country=country,
                sources=["aliexpress", "amazon", "temu", "shopee"],
                limit_per_source=8,
            )
            for source_name, products in extra_results.items():
                if isinstance(products, list):
                    scraped_data[source_name] = products
                elif isinstance(products, str):
                    # Es un error string (source_error)
                    scraped_data[source_name] = products
        except Exception as e:
            scraped_data["extra_sources_error"] = str(e)

        # 2. Inyectar datos scrapeados en el contexto
        enriched_context = {**context}
        enriched_context["_scraped_data"] = scraped_data
        enriched_context["_scraped_at"] = datetime.now(timezone.utc).isoformat()

        total_sources = sum(
            len(v) for v in scraped_data.values() if isinstance(v, list)
        )

        # 3. Ejecutar LLM con datos reales
        messages = self.build_messages(user_input, enriched_context)
        model = model_override or self.default_model

        result = await self._client.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=self.system_prompt,
        )

        # 4. Enriquecer resultado con metadata de scraping
        result["scraped_sources"] = {
            "mercadolibre_count": len(scraped_data.get("mercadolibre", [])),
            "google_shopping_count": len(scraped_data.get("google_shopping", [])),
            "aliexpress_count": len(scraped_data.get("aliexpress", [])),
            "amazon_count": len(scraped_data.get("amazon", [])),
            "temu_count": len(scraped_data.get("temu", [])),
            "shopee_count": len(scraped_data.get("shopee", [])),
            "total_products_found": total_sources,
            "scraped_at": enriched_context["_scraped_at"],
            "country": country,
        }
        result["raw_scraped_data"] = scraped_data

        return result