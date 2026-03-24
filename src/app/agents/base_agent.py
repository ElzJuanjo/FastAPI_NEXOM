"""
Clase base abstracta para todos los agentes de NexOS.
Soporta historial conversacional para respuestas contextuales.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from infra.tools.openrouter_client import OpenRouterClient


class BaseAgent(ABC):

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @property
    @abstractmethod
    def agent_type(self) -> str:
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    def build_messages(self, user_input: str, context: dict | None = None) -> list[dict]:
        """
        Construye la lista de mensajes para el LLM.
        Incluye historial conversacional si está disponible.
        """
        clean_context = {
            k: v for k, v in (context or {}).items()
            if not k.startswith("_")
        }

        content = user_input
        if clean_context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in clean_context.items())
            content = f"Context:\n{context_str}\n\nRequest: {user_input}"

        return self._build_messages_with_history(content, context)

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.6,
        max_tokens: int = 16384,
    ) -> dict:
        messages = self.build_messages(user_input, context)
        model = model_override or self.default_model

        result = await self._client.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=self.system_prompt,
        )

        # Detectar si la respuesta fue truncada
        if result.get("finish_reason") == "length":
            result["truncated"] = True
            result["content"] = (result.get("content") or "") + "\n\n---\n⚠️ *Response truncated due to limit.*"
        else:
            result["truncated"] = False

        return result
    

    def _build_messages_with_history(self, user_content: str, context: dict | None = None) -> list[dict]:
        """
        Construye mensajes incluyendo historial conversacional.
        Para agentes con build_messages custom que necesitan inyectar datos extra.
        """
        messages = []

        # Incluir historial conversacional
        if context and "_conversation_history" in context:
            history = context["_conversation_history"]
            recent = history[-10:] if len(history) > 10 else history
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if len(content) > 1500:
                    content = content[:1500] + "\n\n[... truncated ...]"
                messages.append({"role": role, "content": content})

        # Agregar el mensaje actual
        messages.append({"role": "user", "content": user_content})

        return messages