"""
Registry de agentes disponibles.
Mapea AgentType a su clase de agente correspondiente.
"""

from infra.tools.openrouter_client import openrouter_client
from .base_agent import BaseAgent
from .product_search_agent import ProductSearchAgent
from .dropi_connector_agent import DropiConnectorAgent
from .general_assistant_agent import GeneralAssistantAgent
from .branding_agent import BrandingAgent
from .copywriting_agent import CopywritingAgent
from .ads_agent import AdsAgent
from .landing_page_agent import LandingPageAgent
from .store_dev_agent import StoreDevAgent
from .image_gen_agent import ImageGenAgent
from .conversion_opt_agent import ConversionOptAgent


_AGENT_MAP: dict[str, BaseAgent] = {
    "product_search": ProductSearchAgent(openrouter_client),
    "dropi_connector": DropiConnectorAgent(openrouter_client),
    "general_assistant": GeneralAssistantAgent(openrouter_client),
    "branding": BrandingAgent(openrouter_client),
    "copywriting": CopywritingAgent(openrouter_client),
    "ads": AdsAgent(openrouter_client),
    "landing_page": LandingPageAgent(openrouter_client),
    "store_dev": StoreDevAgent(openrouter_client),
    "image_gen": ImageGenAgent(openrouter_client),
    "conversion_opt": ConversionOptAgent(openrouter_client),
}


def get_agent(agent_type: str) -> BaseAgent | None:
    return _AGENT_MAP.get(agent_type)


def list_available_agents() -> list[str]:
    return list(_AGENT_MAP.keys())