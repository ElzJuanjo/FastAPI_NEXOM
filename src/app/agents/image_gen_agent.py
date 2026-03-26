"""
Agente de Imágenes — genera imágenes reales usando Gemini.
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
        return """You are a world-class visual content generator for E-Commerce and branding.
You generate exactly what the user describes, adapting your output to the type of visual requested.

You MUST detect the type of image requested and adapt accordingly:

TYPE DETECTION:
- LOGO/BRANDING: If the user mentions "logo", "logotipo", "marca", "brand mark", "isotipo", "wordmark", "icon" → Generate a clean, professional logo design. NO product photography styling. Use solid or gradient backgrounds. The logo must be the ONLY element. No scenes, no products, no lifestyle.
- PRODUCT PHOTOGRAPHY: If the user mentions a physical product, "product photo", "fotografía de producto" → Professional product photography with appropriate lighting and background.
- AD CREATIVE: If the user mentions "ad", "anuncio", "banner", "creative" → Marketing-ready visual with text space considerations.
- SOCIAL MEDIA: If the user mentions "post", "story", "reel", "feed" → Platform-optimized visual.
- GENERAL: For anything else, generate the most appropriate visual.

LOGO-SPECIFIC RULES (when type is LOGO/BRANDING):
- Generate ONLY the logo, nothing else in the image
- Clean background (solid color, subtle gradient, or transparent-style)
- The logo must be centered and prominent
- Follow any brand guidelines provided in context (colors, style, concept)
- Make it look like a real, professional logo designed by a top agency
- If the user asks for "just the logo" or "only the content", generate the logo isolated on a plain background with NO mockups, NO scenes, NO 3D effects
- Use the EXACT brand colors if specified in the conversation history

PRODUCT PHOTOGRAPHY RULES (when type is PRODUCT):
- Professional lighting, commercial-ready
- Clean or contextual background as appropriate
- High detail, 4K quality

CRITICAL INTERACTION RULES:
- NEVER repeat a previous image. If the user asks for modifications, apply them to evolve the concept.
- If the user says "now without background" or "just the logo", generate a cleaner version, not the same one.
- Read the FULL conversation history for brand briefs, color palettes, and concepts. They are your creative brief.
- EXECUTE exactly what is asked. Don't add elements the user didn't request.

Respond in the same language the user writes in."""

    # ── Image type detection keywords ─────────────────────────────────────

    LOGO_KEYWORDS = [
        "logo", "logotipo", "isotipo", "wordmark", "marca", "brand mark",
        "icono de marca", "brand icon", "logo design", "diseño de logo",
        "logomark", "símbolo", "symbol", "emblem", "emblema",
    ]

    PRODUCT_KEYWORDS = [
        "producto", "product", "artículo", "item", "packaging",
        "empaque", "botella", "bottle", "caja", "box", "device",
    ]

    def _detect_image_type(self, user_input: str, context: dict) -> str:
        """Detect what type of image the user wants."""
        combined = user_input.lower()

        # Also check recent history for context
        history = context.get("_conversation_history", [])
        for msg in history[-4:]:
            combined += " " + msg.get("content", "").lower()

        for kw in self.LOGO_KEYWORDS:
            if kw in combined:
                return "logo"

        for kw in self.PRODUCT_KEYWORDS:
            if kw in combined:
                return "product"

        return "general"

    # ── History enrichment ────────────────────────────────────────────────

    def _enrich_with_history(self, user_input: str, context: dict) -> str:
        """
        Enriquece el prompt con contexto conversacional completo.
        Busca briefs de branding, descripciones previas, y contexto relevante.
        """
        history = context.get("_conversation_history", [])
        if not history:
            return user_input

        # If input is already very descriptive, use it directly
        if len(user_input) > 300:
            return user_input

        # Collect ALL relevant context from history (not just last message)
        brand_context = []
        last_image_description = ""
        last_user_request = ""

        for msg in reversed(history[-10:]):
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "assistant":
                # Look for brand briefs, logo concepts, color palettes
                content_lower = content.lower()
                has_brand_info = any(kw in content_lower for kw in [
                    "brand book", "paleta", "palette", "color", "tipograf",
                    "logo", "concepto", "concept", "identidad", "identity",
                    "brand", "marca", "hex", "#", "font", "fuente",
                    "isotipo", "wordmark", "slogan", "tagline",
                ])

                if has_brand_info and len(brand_context) < 3:
                    # Extract key info, not the full message
                    extracted = self._extract_brand_info(content)
                    if extracted:
                        brand_context.append(extracted)

                if not last_image_description and "image" in content_lower or "imagen" in content_lower:
                    last_image_description = content[:500]

            elif role == "user" and not last_user_request:
                last_user_request = content[:300]

        # Build enriched prompt
        parts = [f"Current request: {user_input}"]

        if brand_context:
            parts.append(f"\nBrand context from this conversation:\n" + "\n".join(brand_context))

        if last_user_request and last_user_request.lower() != user_input.lower():
            parts.append(f"\nPrevious related request: {last_user_request}")

        if last_image_description:
            parts.append(f"\nPrevious image generated was about: {last_image_description[:300]}")

        parts.append(f"\nGenerate the image following ALL the context above. Apply brand colors, concepts, and style if mentioned.")

        return "\n".join(parts)

    def _extract_brand_info(self, content: str) -> str:
        """Extract key brand information from a long assistant message."""
        lines = content.split("\n")
        key_info = []

        for line in lines:
            line_lower = line.lower().strip()
            # Extract lines with colors, fonts, concepts
            if any(kw in line_lower for kw in [
                "#", "hex", "rgb", "color", "palette", "paleta",
                "font", "tipograf", "fuente", "sora", "manrope", "jakarta",
                "concepto", "concept", "idea central",
                "logo", "isotipo", "wordmark",
                "azul", "blue", "violeta", "violet", "purple",
                "transmitir", "communicate", "represent",
                "minimalista", "minimalist", "geométric", "geometric",
                "dirección", "direction",
            ]):
                cleaned = line.strip()
                if 5 < len(cleaned) < 200:
                    key_info.append(cleaned)

        # Limit to most relevant info
        return "\n".join(key_info[:15]) if key_info else ""

    # ── Prompt builder ────────────────────────────────────────────────────

    def _build_image_prompt(self, user_input: str, context: dict, style: str, image_type: str) -> str:
        """Construye un prompt optimizado según el tipo de imagen."""
        parts = [user_input]

        # Brand context
        brand = context.get("brand", "")
        if brand:
            parts.append(f"Brand: {brand}")

        colors = context.get("colors", "")
        if colors:
            parts.append(f"Brand colors: {colors}")

        # Type-specific quality instructions
        if image_type == "logo":
            parts.append(f"Style: {style}")
            parts.append(
                "This is a LOGO design. Generate ONLY the logo, centered, on a clean background. "
                "Professional, scalable, modern. No product photography. No lifestyle scenes. "
                "No mockups unless explicitly requested. The logo should look like it was designed "
                "by a top branding agency. Sharp vectors, clean geometry, premium feel."
            )
        elif image_type == "product":
            parts.append(f"Style: {style}")
            parts.append("High quality, professional lighting, clean background, commercial ready, 4K detail")
        else:
            parts.append(f"Style: {style}")
            parts.append("High quality, professional, visually striking, commercial ready")

        return ". ".join(parts)

    # ── Execute ───────────────────────────────────────────────────────────

    async def execute(
        self,
        user_input: str,
        context: dict | None = None,
        model_override: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ) -> dict:
        context = context or {}

        # Detect image type
        image_type = self._detect_image_type(user_input, context)

        # Determine style based on type
        if image_type == "logo":
            style = context.get("style", "modern logo design, vector style, clean and professional")
            if context.get("aspect_ratio") is None:
                context["aspect_ratio"] = "1:1"
        else:
            style = context.get("style", "professional product photography")

        aspect_ratio = context.get("aspect_ratio", context.get("format", "1:1"))

        # Enrich with conversation history
        enriched_input = self._enrich_with_history(user_input, context)

        # Build prompt
        prompt = self._build_image_prompt(enriched_input, context, style, image_type)
        model = model_override or self.default_model

        # Generate image
        result = await self._client.image_generation(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            system_prompt=self.system_prompt,
        )

        images = result.get("images", [])
        image_count = len(images)

        # Language detection for response
        input_lower = user_input.lower()
        is_english = any(w in input_lower for w in ["generate", "create", "make", "image", "photo", "picture", "design"])
        is_portuguese = any(w in input_lower for w in ["gerar", "criar", "imagem", "foto"])

        if is_english:
            style_labels = {
                "professional product photography": "Professional product photography",
                "modern logo design, vector style, clean and professional": "Logo design",
                "lifestyle": "Lifestyle", "product_only": "Clean background hero shot",
                "editorial": "Editorial / magazine", "ugc_style": "UGC style",
                "flat_lay": "Flat lay", "detail": "Detail / macro", "context": "Product in context",
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
                "modern logo design, vector style, clean and professional": "Design de logotipo",
                "lifestyle": "Estilo de vida", "product_only": "Produto em fundo limpo",
            }
            format_labels = {
                "1:1": "Quadrado (1:1) — Feed Instagram/Facebook",
                "9:16": "Vertical (9:16) — Stories/Reels/TikTok",
                "16:9": "Horizontal (16:9) — Banner/YouTube",
                "4:5": "Retrato (4:5) — Instagram",
            }
            success_msg = "Imagem gerada" if image_count == 1 else f"{image_count} imagens geradas"
            fail_msg = "Não foi possível gerar a imagem."
        else:
            style_labels = {
                "professional product photography": "Fotografía profesional de producto",
                "modern logo design, vector style, clean and professional": "Diseño de logotipo",
                "lifestyle": "Estilo de vida", "product_only": "Producto en fondo limpio",
                "editorial": "Editorial / revista", "ugc_style": "Estilo UGC",
                "flat_lay": "Vista cenital", "detail": "Detalle / macro", "context": "Producto en contexto",
            }
            format_labels = {
                "1:1": "Cuadrado (1:1) — Feed Instagram/Facebook",
                "9:16": "Vertical (9:16) — Stories/Reels/TikTok",
                "16:9": "Horizontal (16:9) — Banner/YouTube",
                "4:5": "Retrato (4:5) — Instagram",
            }
            success_msg = "Imagen generada" if image_count == 1 else f"{image_count} imágenes generadas"
            fail_msg = "No se pudo generar la imagen. Intenta con una descripción más detallada."

        style_label = style_labels.get(style, style)
        format_label = format_labels.get(aspect_ratio, aspect_ratio)

        content_parts = []
        if image_count > 0:
            content_parts.append(f"✅ {success_msg}. **{'Style' if is_english else 'Estilo'}:** {style_label} **{'Format' if is_english else 'Formato'}:** {format_label}")
        else:
            content_parts.append(f"⚠️ {fail_msg}")

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
                "image_type": image_type,
            },
        }