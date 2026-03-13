"""
Clase base abstracta para todos los agentes de NexOS.
Define el contrato que cada agente debe implementar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from infra.tools.openrouter_client import OpenRouterClient


class BaseAgent(ABC):
    """
    Cada agente define:
    - Su system prompt
    - Su modelo por defecto (overrideable desde AgentConfig)
    - Su lógica de procesamiento de input/output
    """

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Tipo del agente (debe coincidir con AgentType enum)."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Modelo por defecto en formato OpenRouter (ej: 'openai/gpt-4o')."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt de sistema que define el comportamiento del agente."""
        ...

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        """
        Construye la lista de mensajes para el LLM.
        Override en subclases si necesitas lógica custom.
        """
        content = user_input
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            content = f"Contexto:\n{context_str}\n\nSolicitud: {user_input}"

        return [{"role": "user", "content": content}]

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Ejecuta el agente.

        Returns:
            Dict con: content, model, tokens_prompt, tokens_completion, tokens_total, finish_reason
        """
        messages = self.build_messages(user_input, context)
        model = model_override or self.default_model

        result = await self._client.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=self.system_prompt,
        )

        return result