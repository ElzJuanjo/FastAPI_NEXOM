"""
Ejecutor de Flows — corre los steps de un Flow en orden,
respetando dependencias y soportando ejecución paralela por lote.
Emite eventos de progreso vía ProgressEmitter si está disponible.

Imágenes de referencia:
    El router (flow_execute_router) coloca la imagen del usuario en
    `shared_context["input_images"]` y/o `shared_context["reference_image_url"]`.
    Aquí la resolvemos A base64 UNA sola vez antes del primer step y
    analizamos su contenido con un vision model, dejando el resultado
    cacheado en `shared_context["_image_analysis"]` para que todos los
    steps lo reutilicen sin re-descargar ni re-analizar. De esta forma
    los agentes del flow se comportan igual que los del chat: reciben
    la imagen en base64 como contenido multimodal Y un hint textual
    con lo que la imagen representa. Nada se persiste a S3.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.agent_registry import get_agent
from .flow_state import FlowExecutionState
from .flow_planner import build_execution_batches, get_step_context
from .image_context import (
    resolve_images_to_base64,
    analyze_image,
    build_image_hint_for_agent,
)
import logging

logger = logging.getLogger(__name__)


# Agents that benefit from receiving the reference image (as multimodal
# input) and/or a textual hint about its content.
IMAGE_AWARE_AGENTS = {
    "image_gen", "product_search", "branding",
    "copywriting", "ads", "landing_page",
}


async def execute_single_step(
    step: dict,
    step_outputs: dict[str, dict],
    shared_context: dict,
    progress_emitter=None,
    step_index: int = 0,
    total_steps: int = 1,
) -> dict:
    """Ejecuta un step individual invocando su agente."""
    step_id = step["id"]
    agent_type = step["agent_type"]
    step_name = step.get("name", agent_type)
    started_at = datetime.now(timezone.utc)

    # Emit step started
    if progress_emitter:
        pct = int(5 + (step_index / total_steps) * 90)
        await progress_emitter.emit(
            stage="step_started",
            pct=pct,
            agent=agent_type,
            message=f"Running: {step_name}",
            detail=f"Step {step_index + 1}/{total_steps}",
        )

    agent = get_agent(agent_type)

    if not agent:
        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "error",
            "content": f"Agent '{agent_type}' not available",
            "tokens_total": 0,
            "duration_ms": 0,
            "error": f"Agent '{agent_type}' not registered",
        }

    try:
        context = get_step_context(step, step_outputs, shared_context)

        # ── Inyectar imágenes de referencia ya resueltas al contexto ─────
        # El flow las resolvió a base64 UNA sola vez en `prepare_flow_images`
        # y las dejó en shared_context["_resolved_input_images"]. Aquí solo
        # las propagamos al context del step para agentes que las aprovechan.
        # También pasamos el análisis cacheado para que el base_agent pueda
        # inyectarlas como contenido multimodal.
        resolved_images = shared_context.get("_resolved_input_images") or []
        if resolved_images and agent_type in IMAGE_AWARE_AGENTS:
            context["input_images"] = resolved_images
            # image_gen lee `reference_image_url` — lo seteamos al primer
            # base64 para que use esa imagen como referencia directa sin
            # volver a descargar nada.
            if agent_type == "image_gen":
                context["reference_image_url"] = resolved_images[0]
            logger.info(
                f"Flow step {step_id} ({agent_type}): attached "
                f"{len(resolved_images)} resolved reference image(s)"
            )

        # Build a meaningful input from the flow context (incluye hint
        # textual de la imagen cuando hay análisis cacheado).
        user_input = _build_step_input(step, context)

        result = await agent.execute(
            user_input=user_input,
            context=context,
        )

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        # Emit step completed
        if progress_emitter:
            pct = int(5 + ((step_index + 1) / total_steps) * 90)
            content_preview = (result.get("content") or "")[:150]
            await progress_emitter.emit(
                stage="step_completed",
                pct=pct,
                agent=agent_type,
                message=f"Completed: {step_name}",
                detail=content_preview,
            )

        # If image_gen agent, upload images to S3
        images = result.get("images", [])
        uploaded_urls = []

        if agent_type == "image_gen" and images:
            try:
                from infra.tools.s3_client import upload_base64_image
                org_id = shared_context.get("_org_id", "flow")

                for i, img_raw in enumerate(images):
                    # Normalizar: puede ser string base64, URL, o dict OpenAI vision
                    if isinstance(img_raw, dict):
                        img_b64 = (
                            img_raw.get("image_url", {}).get("url")
                            or img_raw.get("url")
                            or img_raw.get("b64_json")
                            or ""
                        )
                    elif isinstance(img_raw, str):
                        img_b64 = img_raw
                    else:
                        logger.warning(f"Flow step {step_id}: unexpected image type {type(img_raw)}, skipping")
                        continue

                    if not img_b64:
                        continue

                    # Si ya es URL pública, no re-subir
                    if img_b64.startswith("http://") or img_b64.startswith("https://"):
                        uploaded_urls.append(img_b64)
                        continue

                    result_s3 = await upload_base64_image(
                        base64_data=img_b64,
                        org_id=org_id,
                        folder="creatives",
                    )
                    if result_s3 and result_s3.get("url"):
                        uploaded_urls.append(result_s3["url"])

                logger.info(f"Flow step {step_id}: uploaded {len(uploaded_urls)} images to S3")
            except Exception as e:
                logger.error(f"Flow step {step_id}: S3 upload failed: {e}")

        # Update content with image URLs if uploaded
        content = result.get("content", "")
        if uploaded_urls:
            content += "\n\n" + "\n".join(f"![Image {i+1}]({url})" for i, url in enumerate(uploaded_urls))

        # Clean prompt_suggestions for image_gen: use the extracted product name
        prompt_suggestions = result.get("prompt_suggestions")
        if agent_type == "image_gen" and prompt_suggestions and isinstance(prompt_suggestions, list):
            # Get the clean product name from context (set by _build_step_input)
            clean_product = context.get("product", "") or context.get("brand", "")
            if clean_product:
                cleaned = []
                for ps in prompt_suggestions:
                    if isinstance(ps, dict) and ps.get("prompt"):
                        cleaned.append({
                            **ps,
                            "prompt": ps["prompt"],  # prompt already uses the clean name from the agent
                        })
                    else:
                        cleaned.append(ps)
                prompt_suggestions = cleaned

        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "completed",
            "content": content,
            "model": result.get("model"),
            "tokens_total": result.get("tokens_total", 0),
            "duration_ms": duration_ms,
            "error": None,
            "scraped_sources": result.get("scraped_sources"),
            "dropi_data": result.get("dropi_data"),
            "images": uploaded_urls if uploaded_urls else images,
            "image_count": result.get("image_count"),
            "generation_params": result.get("generation_params"),
            "prompt_suggestions": prompt_suggestions,
        }

    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        if progress_emitter:
            await progress_emitter.emit(
                stage="step_error",
                pct=int(5 + ((step_index + 1) / total_steps) * 90),
                agent=agent_type,
                message=f"Error: {step_name}",
                detail=str(e)[:200],
            )

        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "error",
            "content": None,
            "tokens_total": 0,
            "duration_ms": duration_ms,
            "error": str(e),
        }


def _build_step_input(step: dict, context: dict) -> str:
    """
    Build a meaningful input for the agent based on flow context.
    Instead of generic "Ejecuta la tarea", use the actual user context.

    Si el flow pasó por una pausa de selección tras product_search, se inyecta
    `selected_products` en el contexto y se usa ESE subset en vez del dump
    completo del agente. Esto asegura que los steps posteriores (image_gen,
    ads, copywriting, etc.) solo trabajen con los productos que el usuario eligió.

    Si el flow arrancó con una imagen de referencia, el análisis cacheado
    en `_image_analysis` se inyecta como hint textual adaptado al agente —
    mismo comportamiento que el chat cuando el input es vago (ver
    executor_node._build_enriched_input).
    """
    step_name = step.get("name", "")
    agent_type = step.get("agent_type", "")

    # Core flow context from user
    brand = context.get("brand", "")
    product = context.get("product", "")
    niche = context.get("niche", "")
    market = context.get("market", "")
    audience = context.get("audience", "")
    tone = context.get("tone", "")

    # Previous step output for continuity
    prev_output = context.get("previous_step_output", "")
    prev_agent = context.get("previous_step_agent", "")

    # ── Productos seleccionados por el usuario tras la pausa ──
    # Si el flow incluyó product_search y el usuario ya eligió, estos son
    # los ÚNICOS productos que deben considerarse hacia adelante.
    selected_products = context.get("selected_products") or []

    # ── image_gen después de product_search: usar el primer producto elegido ──
    if agent_type == "image_gen" and prev_agent == "product_search":
        if selected_products:
            # Tomar el primer producto elegido como referencia principal
            first = selected_products[0]
            if isinstance(first, dict) and first.get("name"):
                product = first["name"]
        elif prev_output:
            winner_name = _extract_top_product_name(prev_output)
            if winner_name:
                product = winner_name

    # ── Hint textual de la imagen de referencia (si la hay) ──
    # El análisis se cachea una sola vez al inicio del flow. Solo lo
    # inyectamos en steps que saben aprovecharlo Y cuando el usuario no
    # ya especificó un `product` explícito (para no duplicar/contradecir).
    image_hint = ""
    analysis = context.get("_image_analysis") or {}
    if analysis and agent_type in (
        "product_search", "image_gen", "branding",
        "copywriting", "ads", "landing_page",
    ):
        # Si el flow ya pasó por product_search y hay seleccionados, el
        # producto del user-pick domina sobre el hint de la imagen.
        if not (selected_products and prev_agent == "product_search"):
            image_hint = build_image_hint_for_agent(analysis, agent_type)
            # Promover product_name del análisis a `product` si el usuario
            # no lo especificó y el step lo necesita.
            if not product and analysis.get("product_name"):
                product = analysis["product_name"]

    # ── product_search con imagen: la query de scraping DEBE ser el
    # search_query concreto extraído de la foto, NO la instrucción
    # genérica ("Search for winning products in the e-commerce niche...").
    # Los scrapers (MercadoLibre, Google Shopping, AliExpress, etc.) usan
    # user_input LITERAL como término de búsqueda. Si entra la instrucción
    # genérica, se termina scrapeando "winning products e-commerce LATAM"
    # y devolviendo resultados sin relación con la foto. El chat lo
    # resuelve en executor_node._build_enriched_input: antepone el
    # search_query de la imagen al input. Aquí replicamos ese mismo
    # contrato en modo flow.
    search_query_override = ""
    if agent_type == "product_search" and analysis:
        search_query_override = (analysis.get("search_query") or "").strip()
        # Si search_query vino vacío pero tenemos product_name, úsalo.
        if not search_query_override and analysis.get("product_name"):
            search_query_override = analysis["product_name"].strip()

    # Build contextual input
    parts = []

    if brand:
        parts.append(f"Brand: {brand}")
    if product:
        parts.append(f"Product: {product}")
    if niche:
        parts.append(f"Niche: {niche}")
    if market:
        parts.append(f"Target market: {market}")
    if audience:
        parts.append(f"Target audience: {audience}")
    if tone:
        parts.append(f"Tone: {tone}")

    context_block = "\n".join(parts) if parts else ""

    # Agent-specific instructions
    instructions = {
        "product_search": f"Search for winning products in the {niche or 'e-commerce'} niche for the {market or 'LATAM'} market. Find products with high demand and good margins.",
        "dropi_connector": f"Search Dropi for products related to: {product or niche or 'trending products'}. Show available suppliers, prices, and stock.",
        "branding": f"Create a complete Brand Book for '{brand or 'the brand'}'. Include: concept, archetype, color palette, typography, tone of voice, key messages, and visual identity guidelines.",
        "copywriting": f"Generate complete sales copy for '{brand or product or 'the brand'}'. Include: headlines, product descriptions, email sequences, social media posts, and CTAs.",
        "image_gen": f"Generate professional product images for '{product or brand or 'the product'}' in a commercial-ready style suitable for e-commerce and social media ads.",
        "ads": f"Create complete ad campaigns for '{brand or product}' targeting {audience or 'the ideal customer'}. Include Meta Ads and Google Ads structures with copy, targeting, and budget recommendations.",
        "landing_page": f"Design a high-conversion landing page for '{brand or product}'. Include hero section, benefits, social proof, FAQ, and CTA sections.",
        "store_dev": f"Configure and recommend the optimal online store setup for '{brand or product}' in the {market or 'LATAM'} market. Include platform, payment gateways, shipping, and technical SEO.",
        "conversion_opt": f"Analyze and recommend conversion optimizations for '{brand or product}'. Include AOV strategies, funnel optimization, CRO recommendations, and tracking setup.",
    }

    instruction = instructions.get(agent_type, f"Execute task: {step_name}")

    # ── DATA-DRIVEN AGENTS (product_search, dropi_connector) ─────────
    # Estos agentes usan `user_input` COMO STRING LITERAL para buscar en
    # APIs externas (MercadoLibre, Google Shopping, AliExpress, Dropi…).
    # Cualquier palabra extra contamina el ranking orgánico y produce
    # resultados distintos (o basura) vs el chat.
    #
    # Rama A — con imagen de referencia (solo product_search hoy):
    #   Devolvemos el mismo formato que `executor_node._build_enriched_input`:
    #
    #       {search_query}
    #
    #       [User request: {step_name or generic}]
    #       [Product identified from image: {product_name}. {description}]
    #
    # Rama B — sin imagen: usamos `product` o `niche` del context del
    #   flow como query directa. Fallback a instrucción legacy solo
    #   cuando no hay ninguna pista útil.
    #
    # El contexto del flow (brand, niche, market, audience, tone) NO se
    # embebe en el user_input — viaja por separado en el dict `context`,
    # que cada agente.build_messages convierte en un bloque "Contexto"
    # para el LLM. Así la API externa recibe solo el query limpio y el
    # LLM recibe todo el contexto. Paridad 1:1 con chat.
    DATA_DRIVEN_AGENTS = {"product_search", "dropi_connector"}

    if agent_type in DATA_DRIVEN_AGENTS:
        # Rama A: imagen disponible (solo product_search la aprovecha hoy,
        # pero el código es agnóstico — si mañana dropi soporta búsqueda
        # por imagen, ya estará listo).
        if search_query_override:
            user_friendly_task = step_name or "Search products related to this image"
            product_name_from_img = (analysis or {}).get("product_name", "").strip()
            description = (analysis or {}).get("description", "").strip()
            chat_compatible_input = search_query_override
            chat_compatible_input += f"\n\n[User request: {user_friendly_task}]"
            if product_name_from_img or description:
                chat_compatible_input += (
                    f"\n[Product identified from image: "
                    f"{product_name_from_img}. {description}]"
                )
            return chat_compatible_input

        # Rama B: sin imagen — usar la pista más específica disponible
        # (product > niche) como query directa de la API externa.
        clean_query = (product or niche or "").strip()
        if clean_query:
            return clean_query
        # Último fallback: instrucción legacy (no rompe flows viejos)

    # Helper to stitch the image hint into the final prompt. Placed in a
    # dedicated block so the agent sees it clearly.
    def _attach_image_hint(base: str) -> str:
        if not image_hint:
            return base
        return f"{base}\n\n[Reference image]\n{image_hint}"

    # ── Si hay selected_products, reemplazamos el dump de prev_output por
    # un resumen compacto de los productos elegidos (más focalizado y ahorra
    # tokens frente a los ~1500 chars del content completo del agente) ──
    if selected_products and prev_agent == "product_search" and agent_type != "image_gen":
        lines = ["Selected products (user-picked from product_search):"]
        for i, sp in enumerate(selected_products[:20], 1):
            if not isinstance(sp, dict):
                continue
            name = sp.get("name", "Unknown")
            score = sp.get("score_total", 0)
            platform = sp.get("source_platform", "")
            price = sp.get("price_usd") or 0
            lines.append(
                f"{i}. {name} | score {score} | {platform} | ~${price} USD"
            )
        selected_summary = "\n".join(lines)
        return _attach_image_hint(
            f"{instruction}\n\n{context_block}\n\n{selected_summary}"
        )

    # Combine everything (comportamiento legacy cuando no hubo selección)
    if prev_output and prev_agent:
        # For image_gen after product_search, don't dump the table — the product name is already in the instruction
        if agent_type == "image_gen" and prev_agent == "product_search":
            return _attach_image_hint(f"{instruction}\n\n{context_block}")
        prev_summary = prev_output[:1500]
        return _attach_image_hint(
            f"{instruction}\n\n{context_block}\n\nPrevious step ({prev_agent}) provided:\n{prev_summary}"
        )
    elif context_block:
        return _attach_image_hint(f"{instruction}\n\n{context_block}")
    else:
        return _attach_image_hint(instruction)
    
    
def _extract_top_product_name(content: str) -> str:
    """Extract the top product name from product_search output.

    Busca primero en el nuevo bloque CANDIDATE_PRODUCTS_JSON; fallback al
    legacy PRODUCT_JSON; último fallback: primera fila de la tabla markdown.
    """
    import re
    import json

    for tag in ("CANDIDATE_PRODUCTS_JSON", "PRODUCT_JSON"):
        match = re.search(
            rf'<!--\s*{tag}\s*(\[.*?\])\s*-->', content, re.DOTALL,
        )
        if match:
            try:
                products = json.loads(match.group(1))
                if isinstance(products, list) and products:
                    best = max(products, key=lambda p: p.get("score_total", 0))
                    name = best.get("name", "").strip()
                    if name:
                        return name
            except (json.JSONDecodeError, ValueError):
                continue

    table_match = re.search(r'\|\s*([^|]{5,80}?)\s*\|\s*\d{2,3}\.?\d*\s*\|', content)
    if table_match:
        name = table_match.group(1).strip().strip("*").strip()
        if name and not name.lower().startswith("product"):
            return name

    return ""


async def _prepare_flow_images(shared_context: dict) -> None:
    """
    One-shot preparation of reference images at the start of a flow run.

    Reads `reference_image_url` and/or `input_images` from shared_context,
    resolves each URL to a base64 data URI, analyzes the first image with
    a vision model to extract a product hint, and caches both in
    shared_context under stable keys:

        _resolved_input_images : list[str]  (base64 data URIs)
        _image_analysis        : dict       (search_query/product_name/...)

    Idempotent: if the cache keys are already populated (e.g. on resume
    after a selection pause), this is a no-op. Errors are swallowed — the
    flow continues without the reference rather than failing outright.
    """
    # Skip if already prepared (resume path).
    if shared_context.get("_resolved_input_images") is not None:
        return

    # Collect candidate URLs from both inputs the router populates.
    candidates: list[str] = []
    ref = shared_context.get("reference_image_url")
    if isinstance(ref, str) and ref:
        candidates.append(ref)

    input_imgs = shared_context.get("input_images") or []
    if isinstance(input_imgs, list):
        for u in input_imgs:
            if isinstance(u, str) and u and u not in candidates:
                candidates.append(u)

    if not candidates:
        # Mark as "processed, nothing found" so we don't retry per-batch.
        shared_context["_resolved_input_images"] = []
        shared_context["_image_analysis"] = {}
        return

    resolved = await resolve_images_to_base64(candidates)
    shared_context["_resolved_input_images"] = resolved

    # Analyze only the first image — matches chat behavior and is cheap.
    analysis: dict = {}
    if resolved:
        try:
            analysis = await analyze_image(resolved[0]) or {}
        except Exception as e:
            logger.warning(f"Flow image analysis failed (continuing without hint): {e}")
            analysis = {}
    shared_context["_image_analysis"] = analysis

    if resolved:
        logger.info(
            f"Flow images prepared: {len(resolved)} base64 image(s), "
            f"analysis={'yes' if analysis else 'no'}"
        )


async def execute_flow(
    state: FlowExecutionState,
    progress_emitter=None,
    resume_from_step_id: str | None = None,
) -> FlowExecutionState:
    """
    Ejecuta un Flow completo, lote por lote.
    Si progress_emitter está presente, emite eventos por cada step.

    PAUSA DE SELECCIÓN DE PRODUCTOS:
    Cuando un step de tipo 'product_search' completa, la ejecución se detiene
    y el flow queda en estado `paused` con los candidatos en `pending_candidates`.
    El usuario debe elegir cuáles productos continúan al resto del flow llamando
    /flows/{id}/resume-with-selection, que invoca esta función de nuevo con
    `resume_from_step_id` apuntando al step siguiente al product_search.

    Args:
        state: FlowExecutionState (puede venir ya parcialmente ejecutado en resume)
        progress_emitter: emisor opcional de eventos SSE
        resume_from_step_id: si se provee, solo se ejecutan los steps DESDE este
            ID en adelante (los previos se consideran ya completados)
    """
    steps = state["steps"]
    step_outputs = dict(state.get("step_outputs", {}))
    shared_context = dict(state.get("shared_context", {}))
    completed_ids = list(state.get("completed_step_ids", []))

    # ── Preparar imágenes de referencia una sola vez ─────────────────
    # Resuelve URLs → base64 y analiza con vision model. Todo cacheado
    # en shared_context para que ningún step tenga que re-descargar ni
    # re-analizar. Idempotente en paths de resume.
    await _prepare_flow_images(shared_context)

    # Si es un resume, filtramos los steps que ya se ejecutaron previamente.
    # Los steps con ID en completed_ids se skippean del batching.
    if resume_from_step_id:
        steps_to_run = [s for s in steps if s["id"] not in completed_ids]
    else:
        steps_to_run = steps

    batches = build_execution_batches(steps_to_run)
    total_steps = len(steps)
    step_counter = len(completed_ids)

    for batch_idx, batch in enumerate(batches):
        tasks = [
            execute_single_step(
                step=step,
                step_outputs=step_outputs,
                shared_context=shared_context,
                progress_emitter=progress_emitter,
                step_index=step_counter + i,
                total_steps=total_steps,
            )
            for i, step in enumerate(batch)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        product_search_result = None

        for result in results:
            if isinstance(result, Exception):
                continue

            step_id = result["step_id"]
            step_outputs[step_id] = result
            completed_ids.append(step_id)

            if result["status"] == "completed" and result.get("content"):
                agent_type = result["agent_type"]
                shared_context[f"step_{agent_type}_result"] = result["content"][:2000]

                # Detectar product_search completado → señal de pausa
                if agent_type == "product_search":
                    product_search_result = result

            if result["status"] == "error":
                state["failed_step_id"] = step_id

        step_counter += len(batch)

        # ── Pausa tras product_search ────────────────────────────────────
        # Solo pausamos si hay MÁS steps pendientes (si product_search es el
        # último, no tiene sentido pausar). También evitamos re-pausar en
        # un resume (los selected_products ya están en shared_context).
        if product_search_result and not resume_from_step_id:
            remaining_steps = [s for s in steps if s["id"] not in completed_ids]
            if remaining_steps:
                # Extraer candidatos del output del agente
                from app.use_cases.product.auto_persist import extract_candidate_products
                content = product_search_result.get("content", "") or ""
                candidates = extract_candidate_products(content) or []

                # ── Sin candidatos → no tiene sentido pausar ni continuar ──
                # Si product_search no devolvió productos, los siguientes
                # agentes no tendrían sobre qué trabajar. Cortamos el flow
                # con error claro en vez de pausar para una selección vacía.
                if not candidates:
                    state["step_outputs"] = step_outputs
                    state["shared_context"] = shared_context
                    state["completed_step_ids"] = completed_ids
                    state["paused"] = False
                    state["completed"] = True
                    state["error"] = (
                        "product_search no encontró productos candidatos. "
                        "Los pasos posteriores no se ejecutaron porque no había "
                        "ningún producto sobre el cual continuar. Ajusta los "
                        "parámetros de búsqueda (niche, market, audience) y "
                        "vuelve a ejecutar el flow."
                    )
                    if progress_emitter:
                        await progress_emitter.emit(
                            stage="step_error",
                            pct=int(5 + (step_counter / total_steps) * 90),
                            agent="product_search",
                            message="No products found — flow stopped",
                            detail="product_search returned 0 candidates; downstream steps skipped",
                        )
                    return state

                state["step_outputs"] = step_outputs
                state["shared_context"] = shared_context
                state["completed_step_ids"] = completed_ids
                state["paused"] = True
                state["pause_reason"] = "awaiting_product_selection"
                state["pause_step_id"] = product_search_result["step_id"]
                state["pending_candidates"] = candidates
                state["completed"] = False

                if progress_emitter:
                    await progress_emitter.emit(
                        stage="awaiting_selection",
                        pct=int(5 + (step_counter / total_steps) * 90),
                        agent="product_search",
                        message="Awaiting product selection",
                        detail=f"{len(candidates)} candidates found — user must select at least 1",
                    )

                return state

    has_errors = any(o.get("status") == "error" for o in step_outputs.values())

    state["step_outputs"] = step_outputs
    state["shared_context"] = shared_context
    state["completed_step_ids"] = completed_ids
    state["completed"] = True
    state["paused"] = False
    if has_errors:
        state["error"] = "One or more steps failed during execution"

    return state