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
from app.agents.scoring import score_products


def _num(value, default: float = 0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
    

class ProductSearchAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "product_search"

    @property
    def default_model(self) -> str:
        return "google/gemini-3-flash-preview"

    @property
    def system_prompt(self) -> str:
        return """You are an expert E-Commerce analyst specialized in identifying winning products for dropshipping.

You are provided REAL product data from multiple sources:
- MercadoLibre and Google Shopping (primary sources — highest volume)
- AliExpress, Amazon, Temu, Shopee (secondary sources — validation)

SCORING SYSTEM — Calculate for each product:
SCORE_TOTAL = (Sales × 0.30) + (Margin × 0.25) + (Trend × 0.20) + (Competition_inv × 0.15) + (Rating × 0.10)
Scale: 0-100. WINNER THRESHOLD: Score ≥ 75/100

WINNING PRODUCT CRITERIA:
- 200+ estimated monthly sales
- Margin >40% (retail price vs supplier price)
- Rating >4.2 stars
- Growth >15% month over month (MoM)

CRITICAL RULES:
- ONLY use the data provided, do NOT invent products or prices
- Always cite the source (platform)
- Compare prices between supplier (AliExpress/Temu) and retail (ML/Amazon/Google Shopping)
- If insufficient data from a source, state it clearly

RESPONSE FORMAT:
1. SCORING TABLE: Product | Score | Est. Sales | Margin | Trend | Competition | Rating | Verdict
2. TOP 3 WINNING PRODUCTS: Those exceeding Score ≥ 75 with justification
3. ARBITRAGE ANALYSIS: Supplier vs retail pricing, cross-platform opportunities
4. COMPETITION ANALYSIS: Saturation level per product
5. RECOMMENDATIONS: Prioritized concrete actions
6. ALERTS: Products to avoid and why

Respond in the same language the user writes in."""

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        """Override: incluye los datos scrapeados con scoring en el mensaje."""
        scraped_data = context.get("_scraped_data", {}) if context else {}
        timestamp = context.get("_scraped_at", "") if context else ""

        parts = [f"Consulta del usuario: {user_input}\n"]

        if context:
            user_context = {k: v for k, v in context.items() if not k.startswith("_")}
            if user_context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in user_context.items())
                parts.append(f"Contexto adicional:\n{context_str}\n")

        if scraped_data:
            parts.append(f"Fecha de consulta: {timestamp}\n")

            # ── Recopilar TODOS los productos de todas las fuentes ──
            all_products = []

            ml_data = scraped_data.get("mercadolibre", [])
            for p in ml_data:
                all_products.append({
                    "name": p.get("name", ""),
                    "price": _num(p.get("price")),
                    "currency": p.get("currency", "COP"),
                    "source": "MercadoLibre",
                    "monthly_sales": _num(p.get("sold_quantity")),
                    "margin_pct": 0,
                    "trend_growth_pct": 0,
                    "competition_level": 5,
                    "rating": _num(p.get("rating")),
                    "seller": p.get("seller", "N/A"),
                    "free_shipping": p.get("free_shipping", False),
                    "url": p.get("url", ""),
                    "reviews_count": p.get("reviews_count", 0),
                })

            gs_data = scraped_data.get("google_shopping", [])
            for p in gs_data:
                all_products.append({
                    "name": p.get("name", ""),
                    "price": _num(p.get("price")),
                    "currency": p.get("currency", "COP"),
                    "source": "MercadoLibre",
                    "monthly_sales": _num(p.get("sold_quantity")),
                    "margin_pct": 0,
                    "trend_growth_pct": 0,
                    "competition_level": 5,
                    "rating": _num(p.get("rating")),
                    "seller": p.get("seller", "N/A"),
                    "url": p.get("url", ""),
                    "reviews_count": p.get("reviews_count", 0),
                })

            for source_key in ["aliexpress", "amazon", "temu", "shopee"]:
                source_data = scraped_data.get(source_key, [])
                for p in source_data:
                    all_products.append({
                        "name": p.get("name", ""),
                        "price": _num(p.get("price")),
                        "currency": p.get("currency", "COP"),
                        "source": "MercadoLibre",
                        "monthly_sales": _num(p.get("sold_quantity")),
                        "margin_pct": 0,
                        "trend_growth_pct": 0,
                        "competition_level": 5,
                        "rating": _num(p.get("rating")),
                        "seller": p.get("seller", "N/A"),
                        "url": p.get("url", ""),
                        "reviews_count": p.get("reviews_count", 0),
                    })

            # ── Aplicar scoring a todos los productos ──
            if all_products:
                scored = score_products(all_products)

                winners = [p for p in scored if p.get("is_winner")]
                potential = [p for p in scored if not p.get("is_winner") and p.get("score_total", 0) >= 50]
                discarded = [p for p in scored if p.get("score_total", 0) < 50]

                parts.append(f"=== RANKING DE PRODUCTOS ({len(scored)} analizados) ===")
                parts.append(f"🏆 Ganadores (≥75): {len(winners)} | ⚡ Potenciales (50-74): {len(potential)} | ❌ Descartados (<50): {len(discarded)}\n")

                for i, p in enumerate(scored[:20], 1):
                    parts.append(
                        f"{i}. {p.get('score_label', '')} {p['name']}\n"
                        f"   Fuente: {p.get('source', 'N/A')}\n"
                        f"   Precio: {p.get('currency', '')} {_num(p.get('price')):,.0f}\n"
                        f"   Score Total: {p.get('score_total', 0)}/100\n"
                        f"   Desglose → Ventas: {p.get('score_breakdown', {}).get('ventas', 0)} | "
                        f"Margen: {p.get('score_breakdown', {}).get('margen', 0)} | "
                        f"Tendencia: {p.get('score_breakdown', {}).get('tendencia', 0)} | "
                        f"Competencia: {p.get('score_breakdown', {}).get('competencia_inv', 0)} | "
                        f"Rating: {p.get('score_breakdown', {}).get('rating', 0)}\n"
                        f"   Rating: {p.get('rating', 'N/A')} | Ventas est: {p.get('monthly_sales', 'N/A')} | Reviews: {p.get('reviews_count', 'N/A')}\n"
                        f"   Vendedor: {p.get('seller', 'N/A')}\n"
                        f"   URL: {p.get('url', '')}"
                    )

            # ── Datos crudos por fuente (referencia para el LLM) ──
            parts.append(f"\n=== RESUMEN POR FUENTE ===")
            parts.append(f"MercadoLibre: {len(ml_data)} productos")
            parts.append(f"Google Shopping: {len(gs_data)} productos")
            for source_key in ["aliexpress", "amazon", "temu", "shopee"]:
                source_data = scraped_data.get(source_key, [])
                if source_data:
                    parts.append(f"{source_key.capitalize()}: {len(source_data)} productos")

        else:
            parts.append(
                "NOTA: No se pudieron obtener datos de scraping. "
                "Responde con tu conocimiento pero indica claramente que los datos NO están verificados en tiempo real."
            )

        return self._build_messages_with_history("\n".join(parts), context)

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 16384,
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