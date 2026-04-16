"""
Filtros de calidad para productos de Dropi.
Basado en los parámetros definidos por el equipo:
- Margen mínimo: 35%
- Tiempo de entrega máximo: 15 días
- Calificación proveedor: ≥ 4.0
"""

from __future__ import annotations


# Parámetros configurables
MIN_MARGIN_PCT = 35.0
MAX_DELIVERY_DAYS = 15
MIN_SUPPLIER_RATING = 4.0
LOW_STOCK_THRESHOLD = 50


def _num(value, default: float = 0) -> float:
    """Convierte a número de forma segura. None y strings inválidos → default."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def calculate_margin(cost: float, suggested_price: float) -> dict:
    """Calcula margen absoluto y porcentual."""
    if cost <= 0:
        return {"margin_cop": 0, "margin_pct": 0}
    margin_cop = suggested_price - cost
    margin_pct = (margin_cop / cost) * 100
    return {
        "margin_cop": round(margin_cop),
        "margin_pct": round(margin_pct, 1),
    }


def evaluate_product(product: dict) -> dict:
    """
    Evalúa un producto de Dropi contra los criterios del equipo.
    
    Retorna el producto enriquecido con:
    - margin_cop, margin_pct: margen calculado
    - alerts: lista de alertas/warnings
    - passes_filters: bool — cumple todos los criterios mínimos
    - quality_score: puntuación simple 0-100
    """
    name = (product.get("name") or "").strip()
    cost = _num(product.get("price"), 0)
    suggested = _num(product.get("suggested_price"), 0)
    stock = _num(product.get("stock"), 0)

    # ── Producto inválido / inexistente ──────────────────────────
    if not name or cost <= 0:
        return {
            **product,
            "margin_cop": 0,
            "margin_pct": 0,
            "alerts": ["🚫 Producto no encontrado o datos incompletos (sin nombre o sin precio)"],
            "passes_filters": False,
            "quality_score": 0,
        }

    margin = calculate_margin(cost, suggested)
    margin_pct = margin["margin_pct"]
    margin_cop = margin["margin_cop"]

    alerts = []
    passes = True

    # Validar margen
    if margin_pct < MIN_MARGIN_PCT:
        alerts.append(f"⚠️ Margen insuficiente: {margin_pct}% (mínimo: {MIN_MARGIN_PCT}%)")
        passes = False
    
    # Validar stock
    if stock <= 0:
        alerts.append("🚫 Sin stock disponible")
        passes = False
    elif stock < LOW_STOCK_THRESHOLD:
        alerts.append(f"⚠️ Stock bajo: {stock} unidades (umbral: {LOW_STOCK_THRESHOLD})")

    # Quality score simple basado en margen y stock
    margin_score = min(margin_pct / 80 * 100, 100) if margin_pct > 0 else 0
    stock_score = min(stock / 500 * 100, 100) if stock > 0 else 0
    quality_score = round(margin_score * 0.6 + stock_score * 0.4, 1)

    return {
        **product,
        "margin_cop": margin_cop,
        "margin_pct": margin_pct,
        "alerts": alerts,
        "passes_filters": passes,
        "quality_score": quality_score,
    }


def evaluate_products(products: list[dict]) -> list[dict]:
    """Evalúa una lista de productos y ordena por quality_score."""
    evaluated = [evaluate_product(p) for p in products]
    evaluated.sort(key=lambda p: p["quality_score"], reverse=True)
    return evaluated


def filter_approved(products: list[dict]) -> list[dict]:
    """Retorna solo productos que pasan todos los filtros."""
    return [p for p in products if p.get("passes_filters", False)]