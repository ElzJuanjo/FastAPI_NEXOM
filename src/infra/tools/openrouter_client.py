"""
Cliente HTTP async para OpenRouter API.
Soporta chat completions con cualquier modelo disponible en OpenRouter.

v2: Multimodal support — image_generation accepts reference_image_url,
    downloads it, converts to base64, injects as vision content so
    Gemini can SEE the real product before generating.
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from infra.config.database import settings

logger = logging.getLogger(__name__)


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
            "HTTP-Referer": "https://nexom.app",
            "X-Title": "NEXOM",
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
        reference_image_url: str | None = None,
    ) -> dict:
        """
        Genera una imagen usando modelos con output_modalities image.

        Args:
            prompt: Descripción de la imagen a generar
            model: Modelo de generación de imágenes
            aspect_ratio: Relación de aspecto (1:1, 16:9, 4:5, 9:16)
            system_prompt: Prompt de sistema opcional
            reference_image_url: URL de imagen de referencia del producto real.
                                 Se descarga, convierte a base64, e inyecta como
                                 contenido multimodal para que el modelo VEA el
                                 producto real antes de generar.

        Returns:
            Dict con: images (list of base64), text (descripción), model, tokens
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # ── Build user message (text-only or multimodal) ──
        if reference_image_url:
            ref_b64 = await self._download_image_as_base64(reference_image_url)

            if ref_b64:
                user_content = [
                    {
                        "type": "image_url",
                        "image_url": {"url": ref_b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "The image above is a REFERENCE PHOTO of the real product. "
                            "Your generated image MUST closely match this product's real "
                            "appearance, shape, colors, textures, and proportions. "
                            "Do NOT invent a different product.\n\n"
                            f"Now generate: {prompt}"
                        ),
                    },
                ]
                messages.append({"role": "user", "content": user_content})
                logger.info("Multimodal reference injected for image generation")
            else:
                messages.append({"role": "user", "content": prompt})
                logger.warning("Reference image download failed, using text-only prompt")
        else:
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
            "HTTP-Referer": "https://nexom.app",
            "X-Title": "NEXOM",
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

        images = []
        text_content = ""

        content = choice.get("message", {}).get("content", "")

        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    images.append(part["image_url"]["url"])
                elif part.get("type") == "text":
                    text_content += part.get("text", "")
        elif isinstance(content, str):
            text_content = content

        msg_images = choice.get("message", {}).get("images", [])
        if msg_images:
            for img in msg_images:
                if isinstance(img, str):
                    images.append(img)
                elif isinstance(img, dict):
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

    # ── Private helpers ───────────────────────────────────────────────────

    async def _download_image_as_base64(self, url: str) -> str | None:
        """
        Download an image from URL and return as data:image/...;base64,... string.
        Returns None if download fails.
        """
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                },
            ) as client:
                response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Image download failed: HTTP {response.status_code} for {url[:80]}")
                return None

            content_type = response.headers.get("content-type", "image/jpeg")
            if ";" in content_type:
                content_type = content_type.split(";")[0].strip()

            if not content_type.startswith("image/"):
                logger.warning(f"Not an image: {content_type} for {url[:80]}")
                return None

            body = response.content
            if len(body) < 1000:
                logger.warning(f"Image too small ({len(body)} bytes), skipping: {url[:80]}")
                return None
            if len(body) > 10 * 1024 * 1024:
                logger.warning(f"Image too large ({len(body)} bytes), skipping: {url[:80]}")
                return None

            b64 = base64.b64encode(body).decode("utf-8")
            return f"data:{content_type};base64,{b64}"

        except Exception as e:
            logger.warning(f"Image download error: {e} for {url[:80]}")
            return None


# Singleton para reutilizar en toda la app
openrouter_client = OpenRouterClient()
