"""
Caso de uso: Generación masiva de creativos publicitarios.
Usa el agente de imágenes con su system_prompt profesional como base,
y genera variaciones controladas de estilo y formato.
La cantidad de imágenes generadas es exacta al preset seleccionado.

v2: Adds product image reference for realistic generation and
    prompt packs with ready-to-use prompts for each creative.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agents.agent_registry import get_agent
from app.agents.credit_costs import get_credit_cost

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variaciones de estilo visual
# ---------------------------------------------------------------------------

STYLES = [
    {"id": "lifestyle", "suffix": "lifestyle photography, natural lighting, real context"},
    {"id": "product_only", "suffix": "clean white background, product hero shot, studio lighting"},
    {"id": "editorial", "suffix": "high-fashion editorial style, magazine quality"},
    {"id": "ugc_style", "suffix": "casual authentic phone-camera feel, user generated content style"},
    {"id": "flat_lay", "suffix": "top-down flat lay arrangement, styled props"},
    {"id": "detail", "suffix": "extreme close-up, texture and craftsmanship detail, macro photography"},
    {"id": "context", "suffix": "product in its ideal environment, contextual lifestyle setting"},
]

FORMATS = [
    {"id": "feed_1x1", "aspect_ratio": "1:1", "platform": "Instagram/Facebook Feed"},
    {"id": "stories_9x16", "aspect_ratio": "9:16", "platform": "Stories/Reels/TikTok"},
    {"id": "portrait_4x5", "aspect_ratio": "4:5", "platform": "Instagram Portrait"},
]

# ---------------------------------------------------------------------------
# Prompt pack templates — ready-to-use prompts for each style
# ---------------------------------------------------------------------------

PROMPT_PACK_TEMPLATES = {
    "product_only": [
        "Professional studio shot of {product} on seamless white background, soft shadow, commercial ready, 4K",
        "{product} floating on gradient background, dramatic rim lighting, premium feel",
        "Minimalist product photography of {product}, neutral gray backdrop, editorial clean",
        "{product} with subtle reflection on glossy surface, luxury packaging shot",
    ],
    "lifestyle": [
        "{product} being used naturally by a person in a cozy home setting, warm tones, authentic",
        "Person confidently using {product} outdoors, golden hour lighting, lifestyle campaign",
        "{product} on a beautiful desk setup, morning coffee vibe, aspirational lifestyle",
        "Close-up of hands interacting with {product}, natural skin tones, genuine moment",
    ],
    "editorial": [
        "High-fashion editorial featuring {product}, Vogue-style composition, dramatic lighting",
        "{product} in a minimalist art gallery setting, conceptual fashion photography",
        "Artistic flat composition with {product} as centerpiece, muted tones, magazine cover worthy",
    ],
    "ugc_style": [
        "Selfie-style photo of person excitedly unboxing {product}, authentic reaction, phone camera feel",
        "Casual overhead shot of {product} on messy desk with coffee and notes, real life aesthetic",
        "Person reviewing {product} in front of ring light, content creator setup, authentic feel",
    ],
    "flat_lay": [
        "Top-down flat lay: {product} surrounded by complementary items and textures, styled arrangement",
        "Knolling composition with {product} and daily essentials, geometric precision, clean background",
    ],
    "detail": [
        "Extreme macro shot of {product} texture and materials, shallow depth of field, craftsmanship",
        "Close-up detail of {product} stitching/buttons/finish, revealing quality and premium materials",
    ],
    "context": [
        "{product} placed naturally in a modern living room, interior design magazine style",
        "{product} in an active outdoor scene, adventure photography, vibrant colors",
    ],
    "video_ideas": [
        "VIDEO CONCEPT: 15s unboxing reveal of {product} — start with package, slow reveal, end with product in use",
        "VIDEO CONCEPT: Before/After comparison using {product} — split screen, dramatic transformation",
        "VIDEO CONCEPT: 30s lifestyle montage — 3 scenes showing {product} in different daily moments",
        "VIDEO CONCEPT: Close-up ASMR-style — unwrapping, touching textures, detailed product showcase",
    ],
}


def generate_prompt_pack(product_name: str, style_id: str) -> list[dict]:
    """Generate a prompt pack for a given product and style."""
    templates = PROMPT_PACK_TEMPLATES.get(style_id, [])
    video_templates = PROMPT_PACK_TEMPLATES.get("video_ideas", [])

    prompts = []
    for tmpl in templates:
        prompts.append({
            "type": "image",
            "style": style_id,
            "prompt": tmpl.format(product=product_name),
        })

    # Always include 1-2 video ideas
    for tmpl in video_templates[:2]:
        prompts.append({
            "type": "video",
            "style": "video",
            "prompt": tmpl.format(product=product_name),
        })

    return prompts


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

BATCH_PRESETS = {
    "starter": {
        "name": "Starter (3 imágenes)",
        "description": "3 variaciones de estilo visual del mismo producto",
        "count": 3,
        "variations": [
            {"style": "product_only", "format": "feed_1x1"},
            {"style": "lifestyle", "format": "feed_1x1"},
            {"style": "editorial", "format": "feed_1x1"},
        ],
    },
    "campaign": {
        "name": "Campaña (5 imágenes)",
        "description": "5 creativos en diferentes estilos y formatos",
        "count": 5,
        "variations": [
            {"style": "product_only", "format": "feed_1x1"},
            {"style": "lifestyle", "format": "feed_1x1"},
            {"style": "editorial", "format": "feed_1x1"},
            {"style": "ugc_style", "format": "stories_9x16"},
            {"style": "context", "format": "stories_9x16"},
        ],
    },
    "full": {
        "name": "Full (10 imágenes)",
        "description": "10 creativos cubriendo todos los estilos y formatos",
        "count": 10,
        "variations": [
            {"style": "product_only", "format": "feed_1x1"},
            {"style": "lifestyle", "format": "feed_1x1"},
            {"style": "editorial", "format": "feed_1x1"},
            {"style": "ugc_style", "format": "feed_1x1"},
            {"style": "flat_lay", "format": "feed_1x1"},
            {"style": "product_only", "format": "stories_9x16"},
            {"style": "lifestyle", "format": "stories_9x16"},
            {"style": "editorial", "format": "stories_9x16"},
            {"style": "detail", "format": "portrait_4x5"},
            {"style": "context", "format": "portrait_4x5"},
        ],
    },
}

STYLE_MAP = {s["id"]: s for s in STYLES}
FORMAT_MAP = {f["id"]: f for f in FORMATS}


def list_presets() -> list[dict]:
    """Lista presets disponibles con su costo en créditos."""
    credit_per_image = get_credit_cost("image_gen")
    return [
        {
            "preset_id": pid,
            "name": preset["name"],
            "description": preset["description"],
            "total_images": preset["count"],
            "credits_cost": preset["count"] * credit_per_image,
        }
        for pid, preset in BATCH_PRESETS.items()
    ]


async def execute_creative_batch(
    product_name: str,
    product_description: str,
    brand_palette: str = "",
    preset_id: str = "starter",
    custom_angles: list[str] | None = None,
    custom_formats: list[str] | None = None,
    custom_styles: list[str] | None = None,
    product_image_url: str = "",
    progress_emitter=None,
) -> dict:
    """
    Ejecuta un batch usando el agente de imágenes.
    Genera exactamente la cantidad de imágenes del preset.
    If product_image_url is provided, it's passed as visual reference
    to generate images based on the real product appearance.
    Also generates a prompt pack with ready-to-use prompts for each variation.
    """
    preset = BATCH_PRESETS.get(preset_id, BATCH_PRESETS["starter"])
    variations = preset["variations"]
    target_count = preset["count"]

    agent = get_agent("image_gen")
    if not agent:
        return {"error": "Image generation agent not available", "images": []}

    base_input = f"{product_name}. {product_description}"
    if brand_palette:
        base_input += f". Brand colors: {brand_palette}"

    # If we have a real product image, instruct the model to use it as reference
    reference_instruction = ""
    if product_image_url:
        reference_instruction = (
            f". IMPORTANT: Use the provided reference image of the real product as the base. "
            f"The generated image MUST closely match the real product's appearance, shape, color, "
            f"and details. Do NOT invent a different product — adapt the REAL product into the requested style. "
            f"Reference image: {product_image_url}"
        )

    results = []
    total_generated = 0
    total_failed = 0
    all_prompt_packs = []

    for idx, variation in enumerate(variations):
        if total_generated >= target_count:
            break

        style_info = STYLE_MAP.get(variation["style"], STYLE_MAP["product_only"])
        format_info = FORMAT_MAP.get(variation["format"], FORMAT_MAP["feed_1x1"])

        # Emit progress
        if progress_emitter:
            pct = int(10 + (idx / target_count) * 80)
            await progress_emitter.emit(
                stage="generating",
                pct=pct,
                message=f"Generating image {idx + 1}/{target_count} — {style_info['id']}",
                detail=f"{format_info['platform']} ({format_info['aspect_ratio']})",
            )

        user_input = f"{base_input}. Style: {style_info['suffix']}{reference_instruction}"

        try:
            context = {
                "aspect_ratio": format_info["aspect_ratio"],
                "style": variation["style"],
            }
            # Pass product image URL in context for multimodal models
            if product_image_url:
                context["reference_image_url"] = product_image_url

            result = await agent.execute(
                user_input=user_input,
                context=context,
            )

            images = result.get("images", [])
            if images:
                img = images[0]
                total_generated += 1

                # Generate prompt pack for this style
                style_prompts = generate_prompt_pack(product_name, variation["style"])

                results.append({
                    "image": img,
                    "angle": variation["style"],
                    "format": variation["format"],
                    "style": variation["style"],
                    "platform": format_info["platform"],
                    "aspect_ratio": format_info["aspect_ratio"],
                    "prompt_used": user_input,
                    "model": result.get("model", ""),
                    "prompt_pack": style_prompts,
                })

                if progress_emitter:
                    pct = int(10 + ((idx + 1) / target_count) * 80)
                    await progress_emitter.emit(
                        stage="image_ready",
                        pct=pct,
                        message=f"Image {total_generated}/{target_count} completed",
                        detail=variation["style"],
                    )
            else:
                total_failed += 1
                logger.warning(f"Batch variation {variation} returned no images")

        except Exception as e:
            total_failed += 1
            logger.error(f"Batch variation {variation} failed: {e}")

    credit_per_image = get_credit_cost("image_gen")

    if progress_emitter:
        await progress_emitter.emit(stage="uploading", pct=92, message="Uploading images to storage...")

    # Collect all unique prompt packs across all generated images
    seen_prompts = set()
    for r in results:
        for p in r.get("prompt_pack", []):
            key = p["prompt"]
            if key not in seen_prompts:
                seen_prompts.add(key)
                all_prompt_packs.append(p)

    return {
        "images": results,
        "total_prompts": len(variations),
        "total_generated": total_generated,
        "total_failed": total_failed,
        "credits_consumed": total_generated * credit_per_image,
        "preset_used": preset_id,
        "prompt_pack": all_prompt_packs,
    }