"""
Motor de scoring para productos ganadores.
Calcula SCORE_TOTAL basado en la fórmula del equipo:

SCORE_TOTAL = (Ventas × 0.30) + (Margen × 0.25) + (Tendencia × 0.20) + (Competencia_inv × 0.15) + (Rating × 0.10)

Cada componente se normaliza a escala 0-100 antes de ponderar.
UMBRAL GANADOR: Score ≥ 75/100
"""

from __future__ import annotations


def _num(value, default: float = 0) -> float:
    """Convierte a número de forma segura. None y strings inválidos → default."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normaliza un valor a escala 0-100."""
    if max_val <= min_val:
        return 50.0
    clamped = max(min_val, min(value, max_val))
    return ((clamped - min_val) / (max_val - min_val)) * 100


def score_product(product: dict) -> dict:
    """
    Calcula el score compuesto de un producto.

    Espera un dict con campos:
    - monthly_sales: ventas estimadas/mes (int)
    - margin_pct: margen porcentual estimado (float, ej: 45.0 = 45%)
    - trend_growth_pct: crecimiento MoM en % (float, ej: 20.0 = 20%)
    - competition_level: nivel de competencia 1-10 (1=baja, 10=alta)
    - rating: rating promedio 0-5

    Retorna el producto enriquecido con:
    - score_total: float 0-100
    - score_breakdown: dict con cada componente
    - is_winner: bool (score >= 75)
    - score_label: str (Ganador / Potencial / Descartado)
    """
    sales = _num(product.get("monthly_sales"), 0)
    margin = _num(product.get("margin_pct"), 0)
    trend = _num(product.get("trend_growth_pct"), 0)
    competition = _num(product.get("competition_level"), 5)
    rating = _num(product.get("rating"), 0)

    # ── Handle incomplete data gracefully ──
    # When sales data is 0 (likely missing, not actually zero), assign a
    # neutral baseline instead of hard-penalizing. Products scraped via
    # Google/SerpAPI often lack "X vendidos" in their snippet, which doesn't
    # mean they have zero sales — it means we couldn't extract the data.
    has_sales_data = sales > 0
    if not has_sales_data:
        # Neutral baseline: 50/100 instead of 0/100 — doesn't reward, doesn't kill
        sales_score = 50.0
    else:
        sales_score = normalize(sales, 0, 1000)

    # Same logic for rating: 0 usually means "not extracted", not "terrible"
    has_rating_data = rating > 0
    if not has_rating_data:
        rating_score = 50.0
    else:
        rating_score = normalize(rating, 0, 5)

    # Normalizar remaining components (0-100)
    margin_score = normalize(margin, 0, 80)          # 0-80% margen
    trend_score = normalize(trend, -10, 50)          # -10% a +50% MoM
    competition_inv = normalize(10 - competition, 0, 10)  # invertir: menos competencia = mejor

    # Fórmula ponderada
    score_total = (
        sales_score * 0.30
        + margin_score * 0.25
        + trend_score * 0.20
        + competition_inv * 0.15
        + rating_score * 0.10
    )

    score_total = round(score_total, 1)

    # Clasificación
    if score_total >= 75:
        label = "🏆 Ganador"
    elif score_total >= 50:
        label = "⚡ Potencial"
    else:
        label = "❌ Descartado"

    return {
        **product,
        "score_total": score_total,
        "score_breakdown": {
            "ventas": round(sales_score, 1),
            "margen": round(margin_score, 1),
            "tendencia": round(trend_score, 1),
            "competencia_inv": round(competition_inv, 1),
            "rating": round(rating_score, 1),
        },
        "is_winner": score_total >= 75,
        "score_label": label,
    }


def score_products(products: list[dict]) -> list[dict]:
    """Aplica scoring a una lista de productos y ordena por score descendente."""
    scored = [score_product(p) for p in products]
    scored.sort(key=lambda p: p["score_total"], reverse=True)
    return scored


def filter_winners(products: list[dict], threshold: float = 75.0) -> list[dict]:
    """Filtra solo productos ganadores."""
    return [p for p in products if p.get("score_total", 0) >= threshold]