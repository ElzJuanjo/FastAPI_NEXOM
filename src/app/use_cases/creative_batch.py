"""
Caso de uso: Generación masiva de creativos publicitarios.
Combina ángulos de venta × formatos × estilos para generar
un batch de imágenes en una sola ejecución.
"""

from __future__ import annotations

from itertools import product as cartesian
from typing import Optional

from app.agents.agent_registry import get_agent
from app.agents.credit_costs import get_credit_cost


# ---------------------------------------------------------------------------
# Configuración de combinaciones
# ---------------------------------------------------------------------------

ANGLES = [
    {"id": "transformation", "prompt_prefix": "Before and after transformation showing the product results,"},
    {"id": "pain", "prompt_prefix": "Visualizing the problem this product solves,"},
    {"id": "social_proof", "prompt_prefix": "Real person happily using the product in everyday life,"},
    {"id": "curiosity", "prompt_prefix": "Eye-catching unexpected visual hook featuring the product,"},
    {"id": "authority", "prompt_prefix": "Professional clinical setting showcasing the product,"},
    {"id": "novelty", "prompt_prefix": "Unboxing new arrival aesthetic with the product,"},
    {"id": "urgency", "prompt_prefix": "Limited edition exclusive feel with the product,"},
]

FORMATS = [
    {"id": "feed_1x1", "aspect_ratio": "1:1", "platform": "Instagram/Facebook Feed"},
    {"id": "stories_9x16", "aspect_ratio": "9:16", "platform": "Stories/Reels/TikTok"},
    {"id": "portrait_4x5", "aspect_ratio": "4:5", "platform": "Instagram Portrait"},
]

STYLES = [
    {"id": "lifestyle", "prompt_suffix": "lifestyle photography, natural lighting, real context"},
    {"id": "product_only", "prompt_suffix": "clean white background, product hero shot, studio lighting"},
    {"id": "editorial", "prompt_suffix": "high-fashion editorial style, magazine quality"},
    {"id": "ugc_style", "prompt_suffix": "casual authentic phone-camera feel, user generated content style"},
    {"id": "flat_lay", "prompt_suffix": "top-down flat lay arrangement, styled props"},
]


# ---------------------------------------------------------------------------
# Presets (combinaciones predefinidas)
# ---------------------------------------------------------------------------

BATCH_PRESETS = {
    "starter": {
        "name": "Starter (5 imágenes)",
        "description": "5 creativos: 1 ángulo × 1 formato × 5 estilos",
        "angles": ["transformation"],
        "formats": ["feed_1x1"],
        "styles": ["lifestyle", "product_only", "editorial", "ugc_style", "flat_lay"],
        "total_images": 5,
    },
    "campaign": {
        "name": "Campaña (15 imágenes)",
        "description": "15 creativos: 5 ángulos × 3 formatos × 1 estilo",
        "angles": ["transformation", "pain", "social_proof", "curiosity", "authority"],
        "formats": ["feed_1x1", "stories_9x16", "portrait_4x5"],
        "styles": ["lifestyle"],
        "total_images": 15,
    },
    "full": {
        "name": "Full (30 imágenes)",
        "description": "30 creativos: 5 ángulos × 3 formatos × 2 estilos",
        "angles": ["transformation", "pain", "social_proof", "curiosity", "authority"],
        "formats": ["feed_1x1", "stories_9x16", "portrait_4x5"],
        "styles": ["lifestyle", "product_only"],
        "total_images": 30,
    },
}


def list_presets() -> list[dict]:
    """Lista presets disponibles con su costo en créditos."""
    credit_per_image = get_credit_cost("image_gen")
    return [
        {
            "preset_id": pid,
            "name": preset["name"],
            "description": preset["description"],
            "total_images": preset["total_images"],
            "credits_cost": preset["total_images"] * credit_per_image,
        }
        for pid, preset in BATCH_PRESETS.items()
    ]


def build_batch_prompts(
    product_name: str,
    product_description: str,
    brand_palette: str = "",
    preset_id: str = "starter",
    custom_angles: list[str] | None = None,
    custom_formats: list[str] | None = None,
    custom_styles: list[str] | None = None,
) -> list[dict]:
    """
    Genera la lista de prompts para un batch de creativos.

    Returns:
        Lista de dicts con: prompt, aspect_ratio, angle, format, style, platform
    """
    preset = BATCH_PRESETS.get(preset_id, BATCH_PRESETS["starter"])

    angle_ids = custom_angles or preset["angles"]
    format_ids = custom_formats or preset["formats"]
    style_ids = custom_styles or preset["styles"]

    angle_map = {a["id"]: a for a in ANGLES}
    format_map = {f["id"]: f for f in FORMATS}
    style_map = {s["id"]: s for s in STYLES}

    prompts = []
    for angle_id, format_id, style_id in cartesian(angle_ids, format_ids, style_ids):
        angle = angle_map.get(angle_id)
        fmt = format_map.get(format_id)
        style = style_map.get(style_id)

        if not all([angle, fmt, style]):
            continue

        prompt = (
            f"{angle['prompt_prefix']} "
            f"{product_name}. {product_description}. "
            f"{style['prompt_suffix']}, "
            f"high quality, commercial ready, 4K detail"
        )

        if brand_palette:
            prompt += f", brand colors: {brand_palette}"

        prompts.append({
            "prompt": prompt,
            "aspect_ratio": fmt["aspect_ratio"],
            "angle": angle_id,
            "format": format_id,
            "style": style_id,
            "platform": fmt["platform"],
        })

    return prompts


async def execute_creative_batch(
    product_name: str,
    product_description: str,
    brand_palette: str = "",
    preset_id: str = "starter",
    custom_angles: list[str] | None = None,
    custom_formats: list[str] | None = None,
    custom_styles: list[str] | None = None,
) -> dict:
    """
    Ejecuta un batch completo de generación de creativos.

    Returns:
        Dict con: images (list), total_generated, total_failed, credits_consumed
    """
    prompts = build_batch_prompts(
        product_name=product_name,
        product_description=product_description,
        brand_palette=brand_palette,
        preset_id=preset_id,
        custom_angles=custom_angles,
        custom_formats=custom_formats,
        custom_styles=custom_styles,
    )

    agent = get_agent("image_gen")
    if not agent:
        return {"error": "Agente de imágenes no disponible", "images": []}

    results = []
    total_generated = 0
    total_failed = 0

    for item in prompts:
        try:
            result = await agent.execute(
                user_input=item["prompt"],
                context={
                    "aspect_ratio": item["aspect_ratio"],
                    "style": item["style"],
                },
            )

            images = result.get("images", [])
            if images:
                total_generated += len(images)
                for img in images:
                    results.append({
                        "image": img,
                        "angle": item["angle"],
                        "format": item["format"],
                        "style": item["style"],
                        "platform": item["platform"],
                        "aspect_ratio": item["aspect_ratio"],
                        "prompt_used": item["prompt"],
                        "model": result.get("model", ""),
                    })
            else:
                total_failed += 1

        except Exception as e:
            total_failed += 1
            results.append({
                "image": None,
                "angle": item["angle"],
                "format": item["format"],
                "style": item["style"],
                "error": str(e),
            })

    credit_per_image = get_credit_cost("image_gen")

    return {
        "images": results,
        "total_prompts": len(prompts),
        "total_generated": total_generated,
        "total_failed": total_failed,
        "credits_consumed": total_generated * credit_per_image,
        "preset_used": preset_id,
    }