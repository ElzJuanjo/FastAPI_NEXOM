"""
Agente de Imágenes — genera imágenes reales de producto usando Gemini.
Usa google/gemini-3.1-flash-image-preview vía OpenRouter.
Retorna imágenes en base64 listas para almacenar o mostrar.
"""

from __future__ import annotations

from .base_agent import BaseAgent


class ImageGenAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "image_gen"

    @property
    def default_model(self) -> str:
        return "google/gemini-3.1-flash-image-preview"

    @property
    def system_prompt(self) -> str:
        return """You are a professional product photographer and creative director for E-Commerce.
Generate high-quality product images based on the description provided.

IMAGE GENERATION RULES:
- Focus on clean, professional, commercial-ready visuals
- Follow the brand palette and style when provided
- Adapt the image to the specified format and platform

CREATIVE SYSTEM BY ANGLE:
- Transformation: before/after visual, show the result
- Pain point: visualize the problem the product solves
- Curiosity: pattern-interrupt, unexpected visual hook
- Social proof: product in real-life context with people
- Authority: clinical/professional setting
- Novelty: unboxing, new arrival aesthetic

AWARENESS LEVELS (adapt visual approach):
1. Unaware → lifestyle/desire imagery
2. Problem aware → visualize the pain
3. Solution aware → product category context
4. Product aware → product hero shot + benefits
5. Most aware → offer/bundle/packaging shot

FORMATS:
- 1:1 → Instagram feed, Facebook feed
- 9:16 → Stories, Reels, TikTok
- 16:9 → Banner, YouTube thumbnail
- 4:5 → Instagram portrait

STYLES:
- lifestyle → product in real-life context
- flat_lay → top-down arrangement
- before_after → split comparison
- mockup → product on device/packaging
- ugc_style → casual, authentic, phone-camera feel
- editorial → high-fashion, magazine quality
- product_only → white/clean background, hero shot

Generate images that are ready-to-use for Meta Ads Manager and TikTok Ads."""

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Genera una imagen real usando Gemini via OpenRouter.
        """
        context = context or {}

        # Determinar aspect ratio del contexto
        aspect_ratio = context.get("aspect_ratio", context.get("format", "1:1"))
        style = context.get("style", "professional product photography")

        # Construir prompt enriquecido
        prompt = self._build_image_prompt(user_input, context, style)
        model = model_override or self.default_model

        # Generar imagen
        result = await self._client.image_generation(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            system_prompt=self.system_prompt,
        )

        # Formatear respuesta
        images = result.get("images", [])
        image_count = len(images)

        return {
            "content": (
                f"Se generó {image_count} imagen(es) exitosamente.\n\n"
                f"Prompt utilizado: {prompt}\n"
                f"Estilo: {style}\n"
                f"Formato: {aspect_ratio}\n"
                f"Modelo: {result.get('model', model)}"
                + (f"\n\nDescripción del modelo: {result.get('text', '')}" if result.get("text") else "")
            ),
            "images": images,
            "image_count": image_count,
            "model": result.get("model", model),
            "tokens_total": result.get("tokens_total", 0),
            "tokens_prompt": result.get("tokens_prompt", 0),
            "tokens_completion": result.get("tokens_completion", 0),
            "finish_reason": "stop",
            "generation_params": {
                "prompt": prompt,
                "style": style,
                "aspect_ratio": aspect_ratio,
            },
        }

    def _build_image_prompt(self, user_input: str, context: dict, style: str) -> str:
        """Construye un prompt optimizado para generación de imágenes."""
        parts = [user_input]

        # Agregar contexto de marca si existe
        brand = context.get("brand", "")
        if brand:
            parts.append(f"Brand: {brand}")

        colors = context.get("colors", "")
        if colors:
            parts.append(f"Brand colors: {colors}")

        # Agregar estilo
        parts.append(f"Style: {style}")

        # Agregar indicaciones de calidad
        parts.append("High quality, professional lighting, clean background, commercial ready, 4K detail")

        return ". ".join(parts)