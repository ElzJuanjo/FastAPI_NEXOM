"""
Tabla de costos en créditos por tipo de agente.
Ajustar estos valores cambia el consumo sin tocar código.
"""

CREDIT_COSTS: dict[str, int] = {
    # Grok (más económico)
    "general_assistant": 1,

    # GPT-5.4 Nano
    "dropi_connector": 2,

    # Gemini Flash
    "product_search": 7,
    "ads": 4,
    "conversion_opt": 4,

    # Gemini Pro
    "landing_page": 14,

    # Image generation
    "image_gen": 15,

    # GPT-5.4 (premium)
    "branding": 17,
    "copywriting": 17,

    # Video (futuro)
    "video_gen": 20,
}

# El costo del router ya está contemplado en el precio de cada agente
ROUTER_CREDIT_COST = 0

# Fallback si el agente no está en la tabla
DEFAULT_CREDIT_COST = 4


def get_credit_cost(agent_type: str) -> int:
    """Retorna el costo en créditos de un tipo de agente."""
    return CREDIT_COSTS.get(agent_type, DEFAULT_CREDIT_COST)


def estimate_flow_credits(agent_types: list[str]) -> int:
    """Estima el costo total en créditos de un flow."""
    return sum(get_credit_cost(at) for at in agent_types)