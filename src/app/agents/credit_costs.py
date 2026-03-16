"""
Tabla de costos en créditos por tipo de agente.
1 crédito ≈ $0.002 USD de costo real.

Ajustar estos valores cambia el consumo sin tocar código.
"""

CREDIT_COSTS: dict[str, int] = {
    # ChatGPT agents (más baratos)
    "product_search": 5,
    "dropi_connector": 5,
    "ads": 5,
    "general_assistant": 1,

    # Claude agents (más caros)
    "branding": 10,
    "copywriting": 10,
    "landing_page": 10,
    "store_dev": 10,
    "conversion_opt": 10,

    # Image generation (el más caro por unidad)
    "image_gen": 15,

    # Video (futuro)
    "video_gen": 20,
}

# Costo del router por cada request al orquestador
ROUTER_CREDIT_COST = 1

# Fallback si el agente no está en la tabla
DEFAULT_CREDIT_COST = 5


def get_credit_cost(agent_type: str) -> int:
    """Retorna el costo en créditos de un tipo de agente."""
    return CREDIT_COSTS.get(agent_type, DEFAULT_CREDIT_COST)


def estimate_flow_credits(agent_types: list[str]) -> int:
    """Estima el costo total en créditos de un flow."""
    return sum(get_credit_cost(at) for at in agent_types)