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
Scale: 0-100.

SCORE BUCKETS (for classification only — ALL are user-selectable):
- WINNER:    Score ≥ 75  → proven demand, ready to launch
- POTENTIAL: Score 50-74 → promising, needs validation
- REJECTED:  Score < 50  → risky or saturated

WINNING PRODUCT CRITERIA (≥75):
- 200+ estimated monthly sales
- Margin >40% (retail price vs supplier price)
- Rating >4.2 stars
- Growth >15% month over month (MoM)

CRITICAL RULES:
- ONLY use the data provided, do NOT invent products or prices
- Compare prices between supplier (AliExpress/Temu) and retail (ML/Amazon/Google Shopping)
- If insufficient data from a source, state it clearly
- HARD LIMIT: The table AND the CANDIDATE_PRODUCTS_JSON block MUST contain
  AT MOST 20 products. If more qualify, pick the 20 with highest score_total.
  The number of rows in the table MUST EQUAL the number of entries in the JSON block.

RESPONSE FORMAT:
1. SCORING TABLE — use this EXACT markdown table format:
   | Product | Score | Bucket | Est. Sales | Margin | Trend | Competition | Rating | Link |

   - Include up to 20 products total (mix of winners, potentials, and rejected if needed).
   - Sort by score_total descending.
   - "Bucket" column values: Winner / Potential / Rejected.

   LINK COLUMN RULES (CRITICAL — READ CAREFULLY):
   - The data already contains pre-formatted markdown links like: [MercadoLibre](https://real-url)
   - You MUST copy these links EXACTLY as-is into the Link column. Do NOT modify them.
   - Do NOT strip the URL and show only the platform name. The link MUST be clickable.
   - Do NOT show the link anywhere else in your response — ONLY in the table and the CANDIDATE_PRODUCTS_JSON block.
   - There is NO separate "Source" or "Fuente" column. The Link IS the source reference.

2. SUMMARY (max 4 lines total — no headers, no bullets):
   - Top pick and why (1 line).
   - Best arbitrage opportunity if any (1 line).
   - Main risk or alert (1 line).
   - One concrete next action (1 line).

Respond in the same language the user writes in.

CRITICAL INTERACTION RULES:
- NEVER offer numbered option menus. Deliver the complete product analysis directly.
- Present all findings in the scoring table format. Don't ask which products to analyze.
- EXECUTE, DON'T ASK. Every message without deliverable content is wasted money.
- Do NOT tell the user products will be "auto-saved" — nothing is auto-saved anymore.
  The user will explicitly pick which products to persist from a selector UI.

─── STRUCTURED DATA BLOCK (MANDATORY) ───

You MUST append ONE HTML comment block at the very end of your response
whenever you have at least 1 analyzed product. The block is invisible to
the user and must appear AFTER all readable content.

<!--CANDIDATE_PRODUCTS_JSON
[
  {
    "name": "Product Name (clean, concise — no emojis, no source prefix)",
    "description": "Brief product description for catalog (1-2 sentences max)",
    "price_usd": 29.99,
    "image_url": "https://actual-image-url-from-the-data",
    "source_platform": "mercadolibre|google_shopping|aliexpress|amazon|temu|shopee",
    "source_url": "https://actual-product-url-from-the-data",
    "score_total": 82.5,
    "score_breakdown": {"ventas": 85, "margen": 70, "tendencia": 90, "competencia_inv": 80, "rating": 88},
    "bucket": "winner",
    "rating": 4.5,
    "monthly_sales": 350,
    "seller": "Seller Name",
    "reviews_count": 120,
    "currency": "COP"
  }
]
-->

RULES FOR THE BLOCK:
- HARD LIMIT: Maximum 20 entries in the array. Pick the 20 with highest score_total.
- "bucket" field values: "winner" (≥75), "potential" (50-74), "rejected" (<50).
- The number of entries MUST equal the number of rows in the markdown table.
- Sort by score_total descending.
- "name" must be a clean product name suitable for a catalog — no emojis, no "🏆", no source prefix.
- "price_usd" should be the price converted to USD (approximate). Use 0 if unknown.
- "image_url" MUST be the actual image URL from the scraped product data
  (mercadolibre/google_shopping/aliexpress/amazon/temu/shopee CDN).
  NEVER use a reference image the user uploaded — that one is provided ONLY
  as visual context for understanding the request/style, NOT for catalog persistence.
  If a candidate has no scraped image, leave the field empty rather than
  fabricating one or reusing the user's upload.
- "source_url" MUST be the actual product URL from the scraped data. NEVER invent or fabricate URLs.
- The JSON must be valid — no trailing commas, no comments inside the JSON arrays.
- If no products were analyzed at all, omit the block entirely.

─── REFERENCE IMAGE HANDLING ───

If the user attached a reference image, USE IT as visual/style context to
refine your product search interpretation. For example, if the image shows
a specific product category (shoes, kitchen gadget, skincare), prioritize
that category in your analysis and table. Mention briefly in section 2
(TOP PICKS) how the reference image influenced your selection.
Do NOT ignore the image. Do NOT copy its URL into any product entry."""

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
                    "image_url": p.get("image_url") or p.get("thumbnail", ""),
                    "reviews_count": p.get("reviews_count", 0),
                })

            gs_data = scraped_data.get("google_shopping", [])
            for p in gs_data:
                all_products.append({
                    "name": p.get("name", ""),
                    "price": _num(p.get("price")),
                    "currency": p.get("currency", "COP"),
                    "source": "Google Shopping",
                    "monthly_sales": _num(p.get("sold_quantity")),
                    "margin_pct": 0,
                    "trend_growth_pct": 0,
                    "competition_level": 5,
                    "rating": _num(p.get("rating")),
                    "seller": p.get("seller", "N/A"),
                    "url": p.get("url", ""),
                    "image_url": p.get("image_url") or p.get("thumbnail", ""),
                    "reviews_count": p.get("reviews_count", 0),
                })

            for source_key in ["aliexpress", "amazon", "temu", "shopee"]:
                source_data = scraped_data.get(source_key, [])
                source_label = source_key.capitalize()
                for p in source_data:
                    all_products.append({
                        "name": p.get("name", ""),
                        "price": _num(p.get("price")),
                        "currency": p.get("currency", "COP"),
                        "source": source_label,
                        "monthly_sales": _num(p.get("sold_quantity")),
                        "margin_pct": 0,
                        "trend_growth_pct": 0,
                        "competition_level": 5,
                        "rating": _num(p.get("rating")),
                        "seller": p.get("seller", "N/A"),
                        "url": p.get("url", ""),
                        "image_url": p.get("image_url") or p.get("thumbnail", ""),
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

                # Send at most 20 products to the LLM, sorted by score_total desc.
                sorted_by_score = sorted(
                    scored,
                    key=lambda p: p.get("score_total", 0),
                    reverse=True,
                )
                relevant = sorted_by_score[:20]
                parts.append(
                    f"NOTA AL LLM: Debes incluir EXACTAMENTE estos {len(relevant)} productos "
                    f"en la tabla y en el bloque CANDIDATE_PRODUCTS_JSON (máximo 20).\n"
                )

                for i, p in enumerate(relevant, 1):
                    raw_url = p.get("url", "").strip()
                    source_name = p.get("source", "N/A")
                    image_url = p.get("image_url", "").strip()

                    # Pre-format the link as markdown so the LLM copies it verbatim
                    if raw_url and raw_url.startswith("http"):
                        link_md = f"[{source_name}]({raw_url})"
                    else:
                        link_md = source_name

                    parts.append(
                        f"{i}. {p.get('score_label', '')} {p['name']}\n"
                        f"   Precio: {p.get('currency', '')} {_num(p.get('price')):,.0f}\n"
                        f"   Score Total: {p.get('score_total', 0)}/100\n"
                        f"   Desglose → Ventas: {p.get('score_breakdown', {}).get('ventas', 0)} | "
                        f"Margen: {p.get('score_breakdown', {}).get('margen', 0)} | "
                        f"Tendencia: {p.get('score_breakdown', {}).get('tendencia', 0)} | "
                        f"Competencia: {p.get('score_breakdown', {}).get('competencia_inv', 0)} | "
                        f"Rating: {p.get('score_breakdown', {}).get('rating', 0)}\n"
                        f"   Rating: {p.get('rating', 'N/A')} | Ventas est: {p.get('monthly_sales', 'N/A')} | Reviews: {p.get('reviews_count', 'N/A')}\n"
                        f"   Vendedor: {p.get('seller', 'N/A')}\n"
                        f"   Link: {link_md}\n"
                        f"   Imagen: {image_url}"
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

    # ── Generic query detection ─────────────────────────────────────────
    _GENERIC_PATTERNS = [
        "busca productos", "buscar productos", "encuentra productos",
        "productos ganadores", "productos trending", "winning products",
        "find products", "search products", "qué se vende", "que se vende",
        "qué vender", "que vender", "productos para vender",
        "productos rentables", "top productos", "mejores productos",
    ]

    def _is_generic_query(self, user_input: str) -> bool:
        """Detect if query is too generic (no specific niche/product)."""
        low = user_input.lower().strip()
        # Exact match or very short
        if len(low) < 20:
            for pat in self._GENERIC_PATTERNS:
                if pat in low:
                    return True
        # If it's just "busca productos" or similar with no qualifiers
        if any(low == pat for pat in self._GENERIC_PATTERNS):
            return True
        return False

    def _enrich_query_for_bestsellers(self, user_input: str, country: str) -> str:
        """For generic queries, append 'más vendidos' to improve results."""
        low = user_input.lower()
        if any(kw in low for kw in ["más vendido", "mas vendido", "best sell", "top sell", "trending"]):
            return user_input  # Already has qualifier
        return f"{user_input} más vendidos"

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
        is_generic = self._is_generic_query(user_input)

        # 1. Scraping real
        scraped_data = {}

        # MercadoLibre (siempre disponible, sin API key)
        try:
            ml_query = self._enrich_query_for_bestsellers(user_input, country) if is_generic else user_input
            ml_results = await mercadolibre_client.search_products(
                query=ml_query,
                country=country,
                limit=15,
                sort="relevance",
            )

            if is_generic:
                products_with_sales = [p for p in ml_results if (p.get("sold_quantity") or 0) > 0]
                if len(products_with_sales) < 3:
                    for trending_q in ["gadgets más vendidos", "accesorios trending", "hogar más vendidos"]:
                        try:
                            extra_ml = await mercadolibre_client.search_products(
                                query=trending_q, country=country, limit=5, sort="relevance",
                            )
                            ml_results.extend(extra_ml)
                        except Exception:
                            pass
                    seen_urls = set()
                    deduped = []
                    for p in ml_results:
                        url = p.get("url", "")
                        if url not in seen_urls:
                            seen_urls.add(url)
                            deduped.append(p)
                    ml_results = deduped

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

            gs_query = self._enrich_query_for_bestsellers(user_input, country) if is_generic else user_input
            gs_results = await serpapi_client.search_google_shopping(
                query=gs_query,
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