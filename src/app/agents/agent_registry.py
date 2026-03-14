"""
Registry de agentes disponibles.
Mapea AgentType a su clase de agente correspondiente.
"""

from infra.tools.openrouter_client import openrouter_client
from .base_agent import BaseAgent
from .product_search_agent import ProductSearchAgent
from .dropi_connector_agent import DropiConnectorAgent


# Mapeo de agent_type -> instancia del agente
_AGENT_MAP: dict[str, BaseAgent] = {
    "product_search": ProductSearchAgent(openrouter_client),
    "dropi_connector": DropiConnectorAgent(openrouter_client),
}


def get_agent(agent_type: str) -> BaseAgent | None:
    """Obtiene una instancia del agente por su tipo."""
    return _AGENT_MAP.get(agent_type)


def list_available_agents() -> list[str]:
    """Lista los tipos de agente disponibles."""
    return list(_AGENT_MAP.keys())