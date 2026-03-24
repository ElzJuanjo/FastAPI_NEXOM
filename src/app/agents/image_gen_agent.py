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
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Genera una imagen real usando Gemini via OpenRouter.
        Si hay historial conversacional, lo usa para entender el contexto.
        """
        context = context or {}

        # Determinar aspect ratio del contexto
        aspect_ratio = context.get("aspect_ratio", context.get("format", "1:1"))
        style = context.get("style", "professional product photography")

        # Si hay historial, construir un prompt contextualizado
        enriched_input = self._enrich_with_history(user_input, context)

        # Construir prompt enriquecido
        prompt = self._build_image_prompt(enriched_input, context, style)
        model = model_override or self.default_model

        # Generar imagen
        result = await self._client.image_generation(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            system_prompt=self.system_prompt,
        )

        images = result.get("images", [])
        image_count = len(images)

        # Formatear respuesta adaptativa al idioma del input
        input_lower = user_input.lower()
        is_english = any(w in input_lower for w in ["generate", "create", "make", "image", "photo", "picture", "design"])
        is_portuguese = any(w in input_lower for w in ["gerar", "criar", "imagem", "foto"])

        if is_english:
            style_labels = {
                "professional product photography": "Professional product photography",
                "lifestyle": "Lifestyle", "product_only": "Clean background hero shot",
                "editorial": "Editorial / magazine", "ugc_style": "UGC style (authentic content)",
                "flat_lay": "Flat lay (top-down)", "detail": "Detail / macro", "context": "Product in context",
            }
            format_labels = {
                "1:1": "Square (1:1) — Instagram/Facebook Feed",
                "9:16": "Vertical (9:16) — Stories/Reels/TikTok",
                "16:9": "Horizontal (16:9) — Banner/YouTube",
                "4:5": "Portrait (4:5) — Instagram",
            }
            success_msg = "Image generated" if image_count == 1 else f"{image_count} images generated"
            fail_msg = "Could not generate the image. Try a more detailed description."
        elif is_portuguese:
            style_labels = {
                "professional product photography": "Fotografia profissional de produto",
                "lifestyle": "Estilo de vida", "product_only": "Produto em fundo limpo",
                "editorial": "Editorial / revista", "ugc_style": "Estilo UGC (conteúdo autêntico)",
                "flat_lay": "Vista de cima (flat lay)", "detail": "Detalhe / macro", "context": "Produto em contexto",
            }
            format_labels = {
                "1:1": "Quadrado (1:1) — Feed Instagram/Facebook",
                "9:16": "Vertical (9:16) — Stories/Reels/TikTok",
                "16:9": "Horizontal (16:9) — Banner/YouTube",
                "4:5": "Retrato (4:5) — Instagram",
            }
            success_msg = "Imagem gerada" if image_count == 1 else f"{image_count} imagens geradas"
            fail_msg = "Não foi possível gerar a imagem. Tente uma descrição mais detalhada."
        else:
            style_labels = {
                "professional product photography": "Fotografía profesional de producto",
                "lifestyle": "Estilo de vida", "product_only": "Producto en fondo limpio",
                "editorial": "Editorial / revista", "ugc_style": "Estilo UGC (contenido auténtico)",
                "flat_lay": "Vista cenital (flat lay)", "detail": "Detalle / macro", "context": "Producto en contexto",
            }
            format_labels = {
                "1:1": "Cuadrado (1:1) — Feed Instagram/Facebook",
                "9:16": "Vertical (9:16) — Stories/Reels/TikTok",
                "16:9": "Horizontal (16:9) — Banner/YouTube",
                "4:5": "Retrato (4:5) — Instagram",
            }
            success_msg = "Imagen generada" if image_count == 1 else f"{image_count} imágenes generadas"
            fail_msg = "No se pudo generar la imagen. Intenta con una descripción más detallada."

        style_es = style_labels.get(style, style)
        format_es = format_labels.get(aspect_ratio, aspect_ratio)

        content_parts = []
        if image_count > 0:
            content_parts.append(f"✅ {success_msg}.")
        else:
            content_parts.append(f"⚠️ {fail_msg}")

        content_parts.append(f"**{'Style' if is_english else 'Estilo'}:** {style_es}")
        content_parts.append(f"**{'Format' if is_english else 'Formato'}:** {format_es}")

        if result.get("text"):
            content_parts.append(f"\n{result['text']}")

        return {
            "content": "\n".join(content_parts),
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

    def _enrich_with_history(self, user_input: str, context: dict) -> str:
        """
        Enriquece el prompt con contexto conversacional.
        Si el mensaje es corto o referencial, incluye el último intercambio
        para que el modelo de imágenes entienda qué se pide.
        """
        history = context.get("_conversation_history", [])
        if not history:
            return user_input

        # Si el input ya es suficientemente descriptivo (>200 chars), usarlo directo
        if len(user_input) > 200:
            return user_input

        # Extraer el último mensaje del assistant y el último del user
        # para entender el contexto inmediato
        last_assistant = ""
        last_user_request = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant" and not last_assistant:
                last_assistant = msg.get("content", "")
            elif msg.get("role") == "user" and not last_user_request:
                last_user_request = msg.get("content", "")
            if last_assistant and last_user_request:
                break

        # Truncar
        if len(last_assistant) > 1000:
            last_assistant = last_assistant[:1000]
        if len(last_user_request) > 300:
            last_user_request = last_user_request[:300]

        # Construir prompt con contexto
        enriched = (
            f"Previous context in this conversation:\n"
            f"- User previously asked: {last_user_request}\n"
            f"- Assistant responded with an image/content about: {last_assistant[:500]}\n\n"
            f"Now the user wants: {user_input}\n\n"
            f"Generate an image that follows from the previous context. "
            f"If the user is asking for a modification of the previous image, "
            f"keep the same subject and style but apply the requested change."
        )

        return enriched

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