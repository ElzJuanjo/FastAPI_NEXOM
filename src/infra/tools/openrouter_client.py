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
        max_tokens: int = 8192,
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
        
    async def image_generation(
        self,
        prompt: str,
        model: str = "google/gemini-3.1-flash-image-preview",
        aspect_ratio: str = "1:1",
        system_prompt: str | None = None,
    ) -> dict:
        """
        Genera una imagen usando modelos con output_modalities image.

        Args:
            prompt: Descripción de la imagen a generar
            model: Modelo de generación de imágenes
            aspect_ratio: Relación de aspecto (1:1, 16:9, 4:5, 9:16)
            system_prompt: Prompt de sistema opcional

        Returns:
            Dict con: images (list of base64), text (descripción), model, tokens
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": aspect_ratio,
            },
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

        # Extraer imágenes y texto del response
        images = []
        text_content = ""

        content = choice.get("message", {}).get("content", "")

        # El content puede ser string o array de parts
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    images.append(part["image_url"]["url"])
                elif part.get("type") == "text":
                    text_content += part.get("text", "")
        elif isinstance(content, str):
            text_content = content

        # También buscar en el campo images directo
        msg_images = choice.get("message", {}).get("images", [])
        if msg_images:
            for img in msg_images:
                if isinstance(img, str):
                    images.append(img)
                elif isinstance(img, dict):
                    # Normalizar dict → string base64/URL
                    url = (
                        img.get("image_url", {}).get("url")
                        or img.get("url")
                        or img.get("b64_json")
                        or ""
                    )
                    if url:
                        images.append(url)

        return {
            "images": images,
            "text": text_content,
            "model": data.get("model", model),
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_completion": usage.get("completion_tokens", 0),
            "tokens_total": usage.get("total_tokens", 0),
        }


# Singleton para reutilizar en toda la app
openrouter_client = OpenRouterClient()