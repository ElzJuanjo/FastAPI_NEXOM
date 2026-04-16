"""
Motor de scoring para productos ganadores.
Calcula SCORE_TOTAL basado en la fórmula del equipo:

SCORE_TOTAL = (Ventas × 0.30) + (Margen × 0.25) + (Tendencia × 0.20) + (Competencia_inv × 0.15) + (Rating × 0.10)

Cada componente se normaliza a escala 0-100 antes de ponderar.
UMBRAL GANADOR: Score ≥ 75/100

v3: Weight-normalized scoring for uneven data quality.
    Cada componente del score tiene una flag `has_data` real (vs valor
    asumido/neutral). Los componentes SIN datos reales no aportan al
    score final: ni suman ni restan. Luego el score se re-escala al
    100% usando SOLO los pesos de los componentes que sí tenían data
    real.

    Ejemplo: un producto de Google Shopping con ventas + rating reales
    pero sin margen/tendencia/competencia reales tenía en v2 un score
    tope de ~72 (porque los tres campos asumidos lo arrastraban a
    neutral). En v3, el mismo producto con ventas=900 y rating=4.7
    puede llegar a ~92 si esos son realmente sus números.

    Esto elimina el síntoma "todos empatados en 74" que aparecía cuando
    el scoring promediaba forzosamente con componentes neutrales.

    Para que la normalización sea estable, se exige un mínimo de peso
    con datos reales (MIN_WEIGHT_COVERAGE). Si el producto tiene datos
    en menos que eso, cae al comportamiento legacy (v2) para evitar
    scores inflados por UN SOLO dato excelente.
"""

from __future__ import annotations


# Mínimo de peso ponderado que debe tener datos reales para activar la
# normalización. 0.40 = al menos el 40% de los componentes (ponderados)
# deben tener datos confiables. Por debajo, caemos al scoring legacy
# neutral para no inflar el score con UN solo campo bueno.
MIN_WEIGHT_COVERAGE = 0.40


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
    - reviews_count: número de reviews (used as sales proxy)
    - free_shipping: boolean

    Retorna el producto enriquecido con:
    - score_total: float 0-100
    - score_breakdown: dict con cada componente
    - is_winner: bool (score >= 75)
    - score_label: str (Ganador / Potencial / Descartado)
    - data_coverage: float 0-1 (proporción de peso con datos reales)
    """
    sales = _num(product.get("monthly_sales"), 0)
    margin = _num(product.get("margin_pct"), 0)
    trend = _num(product.get("trend_growth_pct"), 0)
    competition = _num(product.get("competition_level"), 5)
    rating = _num(product.get("rating"), 0)
    reviews_count = _num(product.get("reviews_count"), 0)
    free_shipping = product.get("free_shipping", False)

    # ── Componentes: (score_value, weight, has_real_data) ─────────
    # has_real_data marca si el scraper nos entregó el dato o si
    # estamos asumiendo un valor neutral. Solo los que tienen data
    # real participan en la normalización v3.

    # Sales: real si vino sold_quantity; proxy si reviews>0; falso si nada.
    if sales > 0:
        sales_score = normalize(sales, 0, 1000)
        sales_has_data = True
    elif reviews_count > 0:
        # Reviews como proxy conservador (reviews ≈ 3-8% de ventas)
        estimated_sales = reviews_count * 5
        sales_score = normalize(estimated_sales, 0, 1000)
        sales_has_data = True  # reviews SON un dato real
    else:
        sales_score = 50.0
        sales_has_data = False

    # Rating
    if rating > 0:
        rating_score = normalize(rating, 0, 5)
        rating_has_data = True
    elif reviews_count > 10:
        # Hay reviews pero no rating → asumimos decente (3.8+)
        rating_score = 70.0
        rating_has_data = False  # asumido
    else:
        rating_score = 50.0
        rating_has_data = False

    # Margin: requiere precio proveedor vs retail. Raramente disponible.
    if margin > 0:
        margin_score = normalize(margin, 0, 80)
        margin_has_data = True
    else:
        margin_score = 55.0  # baseline neutral-positivo
        margin_has_data = False

    # Trend: requiere histórico. Raramente disponible.
    if trend != 0:
        trend_score = normalize(trend, -10, 50)
        trend_has_data = True
    else:
        # High-sales como proxy débil — lo dejamos como señal pero sin
        # marcarlo como "data real" para no inflar el score
        if sales > 200 or reviews_count > 50:
            trend_score = 65.0
        else:
            trend_score = 50.0
        trend_has_data = False

    # Competition: competition_level viene con default 5 del scraper,
    # casi nunca es un dato real. Lo marcamos como asumido.
    competition_inv = normalize(10 - competition, 0, 10)
    competition_has_data = False

    # ── Bonus: free shipping ─────────────────────────────────────
    shipping_bonus = 3.0 if free_shipping else 0.0

    # ── v3: scoring normalizado al peso disponible ───────────────
    weights = {
        "ventas": (sales_score, 0.30, sales_has_data),
        "margen": (margin_score, 0.25, margin_has_data),
        "tendencia": (trend_score, 0.20, trend_has_data),
        "competencia_inv": (competition_inv, 0.15, competition_has_data),
        "rating": (rating_score, 0.10, rating_has_data),
    }

    real_weight = sum(w for _, w, has in weights.values() if has)

    # Score legacy (v2): promedio ponderado con TODOS los componentes,
    # incluyendo los asumidos/neutrales.
    legacy_score = (
        sales_score * 0.30
        + margin_score * 0.25
        + trend_score * 0.20
        + competition_inv * 0.15
        + rating_score * 0.10
    )

    if real_weight >= MIN_WEIGHT_COVERAGE:
        # Score normalizado (v3): solo componentes con datos reales,
        # re-escalados al 100%.
        weighted_sum = sum(
            score * w
            for score, w, has in weights.values()
            if has
        )
        normalized_score = weighted_sum / real_weight

        # Blending: cuando la cobertura es baja (cerca del mínimo),
        # mezclamos con el legacy para que un solo dato excelente no
        # infle el score de forma agresiva. A mayor cobertura, más
        # peso tiene la versión normalizada.
        #
        #   cobertura 0.40 → 50% normalized + 50% legacy
        #   cobertura 0.70 → 75% normalized + 25% legacy
        #   cobertura 1.00 → 100% normalized (equivale a v2 exacto)
        blend_ratio = min(1.0, (real_weight - MIN_WEIGHT_COVERAGE) / 0.6 * 0.5 + 0.5)
        score_total = normalized_score * blend_ratio + legacy_score * (1 - blend_ratio)
    else:
        # Muy poca data real → usar legacy completo. Evita que UN solo
        # dato bueno cree un score engañosamente alto.
        score_total = legacy_score

    score_total += shipping_bonus

    score_total = round(min(score_total, 100.0), 1)
    data_coverage = round(real_weight, 2)

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
        "data_coverage": data_coverage,
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
