"""
Factory para crear instancias de ChatModel que hablan con OpenRouter.
"""

from langchain_openai import ChatOpenAI

from infra.config.database import settings


def get_chat_model(
    model: str = "x-ai/grok-4.1-fast",
    temperature: float = 0.7,
    max_tokens: int = 16384,
) -> ChatOpenAI:
    """
    Crea un ChatModel apuntando a OpenRouter.
    Soporta cualquier modelo disponible en OpenRouter.
    """
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://nexom.app",
            "X-Title": "NEXOM",
        },
    )