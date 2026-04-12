"""
Nodo Executor — ejecuta el agente seleccionado por el router.
Pasa el historial conversacional al agente para que tenga contexto.
Pre-procesa imágenes de input: las resuelve a base64 y genera una
descripción textual para que TODOS los agentes puedan usarla.
"""

from __future__ import annotations

import logging

from app.agents.agent_registry import get_agent
from .state import OrchestratorState

logger = logging.getLogger(__name__)


async def _resolve_images_to_base64(image_urls: list[str]) -> list[str]:
    """
    Descarga URLs de imágenes y las convierte a base64 data URIs.
    Se hace UNA sola vez en el executor, antes de pasar a cualquier agente.
    """
    if not image_urls:
        return []

    from infra.tools.openrouter_client import openrouter_client

    resolved = []
    for url in image_urls:
        if url.startswith("data:"):
            resolved.append(url)
        else:
            try:
                b64 = await openrouter_client._download_image_as_base64(url)
                if b64:
                    resolved.append(b64)
                    logger.info(f"Resolved image to base64: {url[:60]}...")
                else:
                    logger.warning(f"Could not resolve image: {url[:60]}")
            except Exception as e:
                logger.warning(f"Error resolving image {url[:60]}: {e}")
    return resolved


async def _analyze_image(b64_image: str) -> dict:
    """
    Usa un modelo de visión para analizar la imagen.
    Retorna un dict con descripción detallada Y un search query limpio.
    """
    from infra.tools.openrouter_client import openrouter_client

    try:
        result = await openrouter_client.chat_completion(
            model="google/gemini-3-flash-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": b64_image},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyze this image and respond with EXACTLY this format (no markdown, no extra text):\n\n"
                            "SEARCH_QUERY: [a short 3-8 word product search query for e-commerce sites, "
                            "include brand and model if visible, e.g. 'Rolex Daytona gold black dial']\n"
                            "PRODUCT_NAME: [specific product name with brand if identifiable]\n"
                            "CATEGORY: [one word: electronics|fashion|accessories|home|beauty|sports|food|toys|other]\n"
                            "DESCRIPTION: [detailed visual description under 100 words: colors, materials, "
                            "shape, distinguishing features, estimated price range]\n"
                        ),
                    },
                ],
            }],
            temperature=0.1,
            max_tokens=400,
        )
        raw = result.get("content", "").strip()
        if not raw:
            return {}

        # Parsear la respuesta estructurada
        analysis = {}
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("SEARCH_QUERY:"):
                analysis["search_query"] = line.split(":", 1)[1].strip()
            elif line.startswith("PRODUCT_NAME:"):
                analysis["product_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("CATEGORY:"):
                analysis["category"] = line.split(":", 1)[1].strip()
            elif line.startswith("DESCRIPTION:"):
                analysis["description"] = line.split(":", 1)[1].strip()

        if analysis:
            logger.info(f"Image analyzed: query='{analysis.get('search_query', '')}' name='{analysis.get('product_name', '')}'")
        return analysis

    except Exception as e:
        logger.warning(f"Image analysis failed: {e}")
        return {}


def _is_vague_input(user_input: str) -> bool:
    """
    Detecta si el texto del usuario es demasiado vago para ser útil
    sin la imagen (ej: 'busca este producto', 'analyze this image').
    """
    vague_patterns = [
        "este producto", "this product", "este artículo", "this item",
        "esta imagen", "this image", "esto", "this", "eso", "that",
        "analiza esto", "analyze this", "busca esto", "search this",
        "genera un creativo", "generate a creative", "crea una imagen",
        "busca este", "search this", "qué es esto", "what is this",
        "búscalo", "find it", "encuéntralo", "look for this",
        "genera", "create", "hazme", "make me",
    ]
    input_lower = user_input.lower().strip()

    # Input muy corto con imagen = probablemente depende de la imagen
    if len(input_lower) < 40:
        for pattern in vague_patterns:
            if pattern in input_lower:
                return True

    # Si solo adjuntó imagen sin texto real
    if input_lower in ("analyze this image", "(imagen adjunta)", ""):
        return True

    return False


def _build_enriched_input(original_input: str, analysis: dict, agent_type: str) -> str:
    """
    Construye un input enriquecido según el tipo de agente.
    Cada agente necesita la información de forma diferente.
    """
    product_name = analysis.get("product_name", "")
    search_query = analysis.get("search_query", "")
    description = analysis.get("description", "")
    category = analysis.get("category", "")

    if agent_type == "product_search":
        # El product_search necesita el search_query como input principal
        # para que el scraper busque bien
        return f"{search_query}\n\n[User request: {original_input}]\n[Product identified from image: {product_name}. {description}]"

    elif agent_type == "image_gen":
        # image_gen necesita saber QUÉ producto generar
        return f"{original_input} — Product: {product_name}. {description}"

    elif agent_type in ("copywriting", "ads"):
        # Copy/ads necesitan contexto del producto
        return f"{original_input}\n\n[Product from image: {product_name} ({category}). {description}]"

    elif agent_type == "landing_page":
        return f"{original_input}\n\n[Product: {product_name} ({category}). {description}]"

    elif agent_type == "branding":
        return f"{original_input}\n\n[Reference product from image: {product_name}. {description}]"

    else:
        # General assistant, conversion_opt, store_dev, dropi, etc.
        return f"{original_input}\n\n[Image analysis: {product_name}. {description}]"


async def executor_node(state: OrchestratorState) -> dict:
    agent_type = state.get("selected_agent")

    if not agent_type or agent_type == "none":
        return {
            "agent_output": {
                "content": "I couldn't identify the right agent for your request. Could you be more specific? / No se identificó un agente adecuado. ¿Puedes ser más específico?",
                "model": "none",
                "tokens_total": 0,
            },
            "completed": True,
        }

    agent = get_agent(agent_type)

    if not agent:
        return {
            "agent_output": {
                "content": f"The agent '{agent_type}' is not available yet. / El agente '{agent_type}' aún no está disponible.",
                "model": "none",
                "tokens_total": 0,
            },
            "completed": True,
        }

    try:
        full_context = state.get("context", {})
        user_input = state["user_input"]

        # Separar historial del resto del contexto
        conversation_history = full_context.get("conversation_history", [])

        # Contexto limpio para el agente (sin keys internas del router)
        user_context = {
            k: v for k, v in full_context.items()
            if not k.startswith("_") and k != "conversation_history"
        }

        # Pasar historial como key especial que base_agent entiende
        if conversation_history:
            user_context["_conversation_history"] = conversation_history

        # ── Pre-resolver imágenes a base64 (universal para todos los agentes) ──
        raw_images = full_context.get("input_images") or []
        if raw_images:
            resolved_images = await _resolve_images_to_base64(raw_images)
            if resolved_images:
                user_context["input_images"] = resolved_images
                logger.info(f"Resolved {len(resolved_images)}/{len(raw_images)} images for agent {agent_type}")

                # ── Analizar imagen y enriquecer input si es vago ──
                if _is_vague_input(user_input):
                    analysis = await _analyze_image(resolved_images[0])
                    if analysis:
                        user_context["_image_analysis"] = analysis
                        user_input = _build_enriched_input(user_input, analysis, agent_type)
                        logger.info(f"Enriched input for {agent_type}: {user_input[:100]}...")

        # Emit progress
        emitter = full_context.get("_progress_emitter")
        if emitter:
            await emitter.emit("generating", 40, agent=agent_type, message=f"Agent {agent_type} processing...")

        result = await agent.execute(
            user_input=user_input,
            context=user_context if user_context else None,
        )

        if emitter:
            await emitter.emit("processing", 80, agent=agent_type, message="Preparing response...")

        return {
            "agent_output": result,
            "completed": True,
        }

    except Exception as e:
        return {
            "agent_output": None,
            "error": str(e),
            "completed": True,
        }