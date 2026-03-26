"""
Caso de uso: Generación masiva de creativos publicitarios.
Usa el agente de imágenes con su system_prompt profesional como base,
y genera variaciones controladas de estilo y formato.
La cantidad de imágenes generadas es exacta al preset seleccionado.
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
    progress_emitter=None,
) -> dict:
    """
    Ejecuta un batch usando el agente de imágenes.
    Genera exactamente la cantidad de imágenes del preset.
    Si progress_emitter está presente, emite progreso por cada imagen.
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

    results = []
    total_generated = 0
    total_failed = 0

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

        user_input = f"{base_input}. Style: {style_info['suffix']}"

        try:
            result = await agent.execute(
                user_input=user_input,
                context={
                    "aspect_ratio": format_info["aspect_ratio"],
                    "style": variation["style"],
                },
            )

            images = result.get("images", [])
            if images:
                img = images[0]
                total_generated += 1
                results.append({
                    "image": img,
                    "angle": variation["style"],
                    "format": variation["format"],
                    "style": variation["style"],
                    "platform": format_info["platform"],
                    "aspect_ratio": format_info["aspect_ratio"],
                    "prompt_used": user_input,
                    "model": result.get("model", ""),
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

    return {
        "images": results,
        "total_prompts": len(variations),
        "total_generated": total_generated,
        "total_failed": total_failed,
        "credits_consumed": total_generated * credit_per_image,
        "preset_used": preset_id,
    }