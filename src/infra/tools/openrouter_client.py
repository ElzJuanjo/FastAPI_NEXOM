"""
Cliente HTTP async para OpenRouter API.
Soporta chat completions con cualquier modelo disponible en OpenRouter.
"""

from __future__ import annotations

from typing import Optional

import httpx

from infra.config.database import settings


class OpenRouterError(Exception):
    """Error en la comunicación con OpenRouter."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenRouter error {status_code}: {detail}")


class OpenRouterClient:

    def __init__(self) -> None:
        self._base_url = settings.OPENROUTER_BASE_URL
        self._api_key = settings.OPENROUTER_API_KEY

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Envía un chat completion a OpenRouter.

        Args:
            model: Modelo a usar (ej: 'openai/gpt-4o', 'anthropic/claude-sonnet-4-20250514', 'google/gemini-pro')
            messages: Lista de mensajes [{"role": "user", "content": "..."}]
            temperature: Creatividad del modelo
            max_tokens: Máximo de tokens en la respuesta
            system_prompt: Prompt de sistema opcional

        Returns:
            Dict con: content, model, tokens_used (prompt + completion), finish_reason
        """
        full_messages = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(messages)

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nexos.app",
            "X-Title": "NexOS",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

        if response.status_code != 200:
            raise OpenRouterError(response.status_code, response.text)

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"]["content"],
            "model": data.get("model", model),
            "finish_reason": choice.get("finish_reason", "unknown"),
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_completion": usage.get("completion_tokens", 0),
            "tokens_total": usage.get("total_tokens", 0),
        }


# Singleton para reutilizar en toda la app
openrouter_client = OpenRouterClient()