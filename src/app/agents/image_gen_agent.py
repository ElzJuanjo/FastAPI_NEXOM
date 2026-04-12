"""
Agente de Imágenes — genera imágenes FOTORREALISTAS usando Gemini.

v4: Auto-reference — busca automáticamente una foto real del producto
    en la web (Bing Images) y la inyecta como referencia multimodal.
    El modelo VE el producto real antes de generar la variación.
"""

from __future__ import annotations

import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ImageGenAgent(BaseAgent):

    @property
    def agent_type(self) -> str:
        return "image_gen"

    @property
    def default_model(self) -> str:
        return "google/gemini-3.1-flash-image-preview"

    @property
    def system_prompt(self) -> str:
        return """You are a world-class commercial product photographer and visual content creator.

CORE PRINCIPLE — PHOTOREALISM ABOVE ALL:
Your #1 job is to generate images that look like REAL PHOTOGRAPHS taken by a professional
photographer with a high-end camera. NOT illustrations, NOT 3D renders, NOT AI-looking images.
Every image must pass the "would a real person scroll past this thinking it's a real photo?" test.

PHOTOREALISM RULES (apply to EVERY product image):
- Shot with a Canon EOS R5 or Sony A7R IV, 85mm f/1.4 lens
- Real studio lighting: 3-point setup with softboxes, fill light, and rim light
- Natural color grading — no oversaturated, no HDR look, no uncanny valley
- Real textures: leather looks like leather, metal has real reflections, fabric has real weave
- Subtle imperfections that make it real: soft shadows, slight depth of field, ambient occlusion
- If the product exists in real life, the image MUST look like a photo of the REAL product,
  not an imagined version. Research what the product actually looks like.
- NO floating products, NO impossible lighting, NO plastic-looking surfaces

TYPE DETECTION — adapt your approach:
- LOGO/BRANDING: If "logo", "logotipo", "marca", "brand mark", "isotipo", "wordmark", "icon" →
  Clean, professional logo design. Vector style, solid/gradient backgrounds. The logo is the ONLY
  element. No product photography. No lifestyle scenes. No mockups unless explicitly requested.

- PRODUCT PHOTOGRAPHY: If a physical product is mentioned →
  Professional product photography. Studio-quality. As if shot for an e-commerce listing.
  The product must look EXACTLY like the real thing.

- AD CREATIVE: If "ad", "anuncio", "banner", "creative" → Marketing-ready visual.
- SOCIAL MEDIA: If "post", "story", "reel", "feed" → Platform-optimized visual.

WHEN A REFERENCE IMAGE IS PROVIDED:
The generated image MUST closely match the real product's appearance, shape, color, texture,
and materials. Do NOT invent a different product. Adapt the REAL product into the requested
style/setting while maintaining 100% visual fidelity to the original.

CRITICAL INTERACTION RULES:
- NEVER repeat a previous image. If the user asks for modifications, evolve the concept.
- Read the FULL conversation history for brand briefs, color palettes, and concepts.
- EXECUTE exactly what is asked. Don't add elements the user didn't request.

Respond in the same language the user writes in."""

    # ── Image type detection ──────────────────────────────────────────────

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
        combined = user_input.lower()
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

    # ── Extract clean product name from user input ────────────────────────

    def _extract_product_name(self, user_input: str) -> str:
        """Extract the product name, removing instruction verbs."""
        name = user_input.strip()
        prefixes = [
            "genera una imagen de", "genera una foto de", "genera un creativo de",
            "crea una imagen de", "crea una foto de", "hazme una imagen de",
            "generate an image of", "create an image of", "make an image of",
            "generate a photo of", "create a photo of", "make a photo of",
            "gerar uma imagem de", "criar uma imagem de",
            "genera", "generate", "create", "crea", "hazme", "make",
            "imagen de", "image of", "foto de", "photo of",
        ]
        name_lower = name.lower()
        for prefix in prefixes:
            if name_lower.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        return name

    # ── History enrichment ────────────────────────────────────────────────

    def _enrich_with_history(self, user_input: str, context: dict) -> str:
        history = context.get("_conversation_history", [])
        if not history or len(user_input) > 300:
            return user_input

        brand_context = []
        last_user_request = ""

        for msg in reversed(history[-10:]):
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "assistant":
                content_lower = content.lower()
                has_brand_info = any(kw in content_lower for kw in [
                    "brand book", "paleta", "palette", "color", "tipograf",
                    "logo", "concepto", "concept", "identidad", "identity",
                    "brand", "marca", "hex", "#", "font", "fuente",
                ])
                if has_brand_info and len(brand_context) < 3:
                    extracted = self._extract_brand_info(content)
                    if extracted:
                        brand_context.append(extracted)
            elif role == "user" and not last_user_request:
                last_user_request = content[:300]

        parts = [f"Current request: {user_input}"]
        if brand_context:
            parts.append(f"\nBrand context:\n" + "\n".join(brand_context))
        if last_user_request and last_user_request.lower() != user_input.lower():
            parts.append(f"\nPrevious request: {last_user_request}")

        return "\n".join(parts)

    def _extract_brand_info(self, content: str) -> str:
        lines = content.split("\n")
        key_info = []
        for line in lines:
            ll = line.lower().strip()
            if any(kw in ll for kw in [
                "#", "hex", "rgb", "color", "palette", "paleta", "font",
                "tipograf", "fuente", "concepto", "concept", "logo",
                "isotipo", "wordmark", "minimalista", "minimalist",
            ]):
                cleaned = line.strip()
                if 5 < len(cleaned) < 200:
                    key_info.append(cleaned)
        return "\n".join(key_info[:15]) if key_info else ""

    # ── Prompt builder ────────────────────────────────────────────────────

    def _build_image_prompt(
        self, user_input: str, context: dict, style: str,
        image_type: str, has_reference: bool,
    ) -> str:
        parts = [user_input]

        brand = context.get("brand", "")
        if brand:
            parts.append(f"Brand: {brand}")
        colors = context.get("colors", "")
        if colors:
            parts.append(f"Brand colors: {colors}")

        if image_type == "logo":
            parts.append(f"Style: {style}")
            parts.append(
                "This is a LOGO design. Generate ONLY the logo, centered, on a clean background. "
                "Professional, scalable, modern. No product photography. No lifestyle scenes."
            )
        elif image_type == "product":
            if has_reference:
                parts.append(
                    f"Style: {style}. "
                    "CRITICAL: A reference photo of the REAL product is provided. "
                    "Your generated image MUST closely match the real product's appearance, shape, "
                    "color, texture, and materials. Adapt the REAL product into the requested style "
                    "while maintaining 100% visual fidelity. Do NOT invent a different product. "
                    "Professional studio photography, Canon EOS R5, 85mm f/1.4."
                )
            else:
                parts.append(
                    f"Style: {style}. "
                    "CRITICAL: This must look like a REAL PHOTOGRAPH, not a render. "
                    "Shot on Canon EOS R5, 85mm f/1.4. Professional 3-point studio lighting. "
                    "Real textures, real reflections, real shadows. 8K, commercial-grade."
                )
        else:
            if has_reference:
                parts.append(
                    f"Style: {style}. "
                    "A reference photo is provided — match the real product's appearance exactly. "
                    "Photorealistic quality, professional photographer, commercial-ready."
                )
            else:
                parts.append(
                    f"Style: {style}. "
                    "Photorealistic quality. Real photograph by a professional photographer. "
                    "Natural lighting, real textures, no AI artifacts. Commercial-ready."
                )

        return ". ".join(parts)

    # ── Prompt suggestions ────────────────────────────────────────────────

    def _generate_prompt_suggestions(
        self, product_name: str, image_type: str, context: dict,
    ) -> list[dict]:
        brand = context.get("brand", "")
        p = product_name
        if brand and brand.lower() not in p.lower():
            p = f"{p} by {brand}"

        if image_type == "logo":
            return [
                {"type": "image", "category": "Logo — Minimal",
                 "prompt": f"Minimalist vector logo for '{p}', single-weight monoline design, geometric forms, scalable at any size, centered on pure white background, Behance award-winning quality"},
                {"type": "image", "category": "Logo — Dark Premium",
                 "prompt": f"Premium logo for '{p}' on matte black background, subtle metallic gold foil effect, luxury brand aesthetic, clean negative space, Dieter Rams inspired simplicity"},
                {"type": "image", "category": "Logo — Gradient Tech",
                 "prompt": f"Modern gradient logo for '{p}', vibrant color transition, tech-startup aesthetic, flat design with depth, SVG-clean edges, Silicon Valley rebrand quality"},
                {"type": "image", "category": "Mockup — Business Card",
                 "prompt": f"Logo of '{p}' embossed on premium kraft paper business card, shallow depth of field, overhead shot on marble surface, natural window light, Canon 5D Mark IV"},
                {"type": "video", "category": "Logo Reveal",
                 "prompt": f"5-second logo reveal animation: particles of light assembling into the '{p}' logo on dark background, cinematic lens flare, dramatic bass hit on reveal"},
            ]

        return [
            {"type": "image", "category": "Hero Shot — White BG",
             "prompt": f"Professional e-commerce hero shot of {p}, seamless white cyclorama background, 3-point studio lighting with large octabox key light, subtle contact shadow, shot on Phase One IQ4 150MP, color-accurate, ready for Amazon/Shopify listing"},
            {"type": "image", "category": "Floating — Gradient",
             "prompt": f"{p} floating at 15-degree angle on smooth gradient background (light gray to white), dramatic rim lighting creating luminous edge, subtle reflection below, clean negative space for text overlay, advertising campaign quality"},
            {"type": "image", "category": "Lifestyle — Golden Hour",
             "prompt": f"Lifestyle editorial: person naturally using {p} in a sunlit modern apartment, golden hour light streaming through floor-to-ceiling windows, warm color palette, shallow depth of field f/2.0, authentic candid moment, Kinfolk magazine aesthetic"},
            {"type": "image", "category": "Macro — Craftsmanship",
             "prompt": f"Extreme macro photograph of {p} showing texture, material quality, and craftsmanship details, 1:1 magnification, focus stacking for edge-to-edge sharpness, reveals stitching/grain/finish, Hasselblad medium format"},
            {"type": "image", "category": "Dark & Premium",
             "prompt": f"{p} on matte black surface, single dramatic spotlight from upper-left creating Rembrandt lighting pattern, deep shadows, luxury brand atmosphere, reflective surface catching subtle light, Rolex/Apple advertising reference"},
            {"type": "image", "category": "Flat Lay — Knolling",
             "prompt": f"Overhead flat lay composition: {p} centered, surrounded by complementary lifestyle props, organized with geometric precision (knolling style), neutral earth-tone palette, soft diffused daylight, Instagram-ready square crop"},
            {"type": "image", "category": "In Context — Editorial",
             "prompt": f"{p} placed naturally in its ideal real-world environment, environmental storytelling, styled like an Architectural Digest product feature, natural ambient lighting, medium-wide shot showing product in context"},
            {"type": "image", "category": "UGC — Authentic",
             "prompt": f"Authentic user-generated content style: person unboxing {p} on their desk, overhead iPhone camera angle, natural messy desk with coffee cup and laptop visible, warm tungsten room lighting, TikTok/Reels aesthetic"},
            {"type": "video", "category": "Unboxing — ASMR",
             "prompt": f"15-second cinematic unboxing: hands carefully opening premium packaging of {p}, ASMR-quality audio of paper and materials, slow reveal building anticipation, ends with hero shot, top-down camera, 4K 60fps"},
            {"type": "video", "category": "360° Showcase",
             "prompt": f"20-second product showcase: {p} rotating smoothly on turntable, studio lighting shifts to highlight different angles and features, camera slowly pushes in from medium to close-up, seamless loop, white infinity curve background"},
            {"type": "video", "category": "Lifestyle Montage",
             "prompt": f"30-second lifestyle montage: 4 scenes showing {p} in different moments of the day (morning routine, commute, work, evening), match-cut transitions, warm-to-cool color grade progression, upbeat lo-fi soundtrack energy"},
        ]

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

        image_type = self._detect_image_type(user_input, context)
        product_name = self._extract_product_name(user_input)

        # Style
        if image_type == "logo":
            style = context.get("style", "modern logo design, vector style, clean and professional")
            if context.get("aspect_ratio") is None:
                context["aspect_ratio"] = "1:1"
        else:
            style = context.get("style", "professional product photography")

        aspect_ratio = context.get("aspect_ratio", context.get("format", "1:1"))

        # ── AUTO-REFERENCE: find real product image if none provided ──
        ref_image_url = (
            context.get("reference_image_url", "")
            or context.get("product_image_url", "")
        )

        if image_type == "logo":
            ref_image_url = ""
        elif not ref_image_url:
            # Primero: usar imagen adjuntada por el usuario
            user_images = (context or {}).get("input_images") or []
            if user_images:
                ref_image_url = user_images[0]
                logger.info(f"Using user-uploaded image as reference: {ref_image_url[:80]}")
            else:
                # Fallback: buscar referencia automáticamente en la web
                try:
                    from infra.tools.image_reference_finder import find_product_reference_image
                    ref_image_url = await find_product_reference_image(user_input) or ""
                    if ref_image_url:
                        logger.info(f"Auto-reference found: {ref_image_url[:80]}")
                except Exception as e:
                    logger.warning(f"Auto-reference search failed: {e}")
                    ref_image_url = ""

        # Enrich with conversation history
        enriched_input = self._enrich_with_history(user_input, context)

        # Build prompt
        has_reference = bool(ref_image_url)
        prompt = self._build_image_prompt(enriched_input, context, style, image_type, has_reference)

        model = model_override or self.default_model

        # Generate image — pass reference for multimodal injection
        result = await self._client.image_generation(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            system_prompt=self.system_prompt,
            reference_image_url=ref_image_url or None,
        )

        images = result.get("images", [])
        image_count = len(images)

        # Language detection
        input_lower = user_input.lower()
        is_english = any(w in input_lower for w in ["generate", "create", "make", "image", "photo", "picture", "design"])
        is_portuguese = any(w in input_lower for w in ["gerar", "criar", "imagem", "foto"])

        if is_english:
            style_labels = {
                "professional product photography": "Professional product photography",
                "modern logo design, vector style, clean and professional": "Logo design",
            }
            format_labels = {"1:1": "Square (1:1)", "9:16": "Vertical (9:16)", "16:9": "Horizontal (16:9)", "4:5": "Portrait (4:5)"}
            success_msg = "Image generated" if image_count == 1 else f"{image_count} images generated"
            fail_msg = "Could not generate the image. Try a more detailed description."
            ref_label = " (based on real product reference)" if has_reference else ""
        elif is_portuguese:
            style_labels = {"professional product photography": "Fotografia profissional de produto"}
            format_labels = {"1:1": "Quadrado (1:1)", "9:16": "Vertical (9:16)"}
            success_msg = "Imagem gerada" if image_count == 1 else f"{image_count} imagens geradas"
            fail_msg = "Não foi possível gerar a imagem."
            ref_label = " (baseada na referência real)" if has_reference else ""
        else:
            style_labels = {
                "professional product photography": "Fotografía profesional de producto",
                "modern logo design, vector style, clean and professional": "Diseño de logotipo",
            }
            format_labels = {"1:1": "Cuadrado (1:1)", "9:16": "Vertical (9:16)", "16:9": "Horizontal (16:9)", "4:5": "Retrato (4:5)"}
            success_msg = "Imagen generada" if image_count == 1 else f"{image_count} imágenes generadas"
            fail_msg = "No se pudo generar la imagen. Intenta con una descripción más detallada."
            ref_label = " (basada en referencia real del producto)" if has_reference else ""

        style_label = style_labels.get(style, style)
        format_label = format_labels.get(aspect_ratio, aspect_ratio)

        content_parts = []
        if image_count > 0:
            content_parts.append(
                f"✅ {success_msg}{ref_label}. "
                f"**{'Style' if is_english else 'Estilo'}:** {style_label} "
                f"**{'Format' if is_english else 'Formato'}:** {format_label}"
            )
        else:
            content_parts.append(f"⚠️ {fail_msg}")

        if result.get("text"):
            content_parts.append(f"\n{result['text']}")

        # Generate prompt suggestions
        prompt_suggestions = self._generate_prompt_suggestions(
            product_name, image_type, context,
        )

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
                "has_reference": has_reference,
                "reference_url": ref_image_url[:200] if ref_image_url else None,
            },
            "prompt_suggestions": prompt_suggestions,
        }
