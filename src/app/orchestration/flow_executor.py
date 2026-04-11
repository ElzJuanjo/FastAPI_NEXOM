"""
Ejecutor de Flows — corre los steps de un Flow en orden,
respetando dependencias y soportando ejecución paralela por lote.
Emite eventos de progreso vía ProgressEmitter si está disponible.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.agent_registry import get_agent
from .flow_state import FlowExecutionState
from .flow_planner import build_execution_batches, get_step_context
import logging

logger = logging.getLogger(__name__)


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

        # Build a meaningful input from the flow context
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

    # ── image_gen after product_search: extract the real product name ──
    if agent_type == "image_gen" and prev_agent == "product_search" and prev_output:
        winner_name = _extract_top_product_name(prev_output)
        if winner_name:
            product = winner_name

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

    # Combine everything
    if prev_output and prev_agent:
        # For image_gen after product_search, don't dump the table — the product name is already in the instruction
        if agent_type == "image_gen" and prev_agent == "product_search":
            return f"{instruction}\n\n{context_block}"
        prev_summary = prev_output[:1500]
        return f"{instruction}\n\n{context_block}\n\nPrevious step ({prev_agent}) provided:\n{prev_summary}"
    elif context_block:
        return f"{instruction}\n\n{context_block}"
    else:
        return instruction
    
    
def _extract_top_product_name(content: str) -> str:
    """Extract the top product name from product_search output."""
    import re
    import json

    match = re.search(r'<!--\s*PRODUCT_JSON\s*(\[.*?\])\s*-->', content, re.DOTALL)
    if match:
        try:
            products = json.loads(match.group(1))
            if isinstance(products, list) and products:
                best = max(products, key=lambda p: p.get("score_total", 0))
                return best.get("name", "").strip()
        except (json.JSONDecodeError, ValueError):
            pass

    table_match = re.search(r'\|\s*([^|]{5,80}?)\s*\|\s*\d{2,3}\.?\d*\s*\|', content)
    if table_match:
        name = table_match.group(1).strip().strip("*").strip()
        if name and not name.lower().startswith("product"):
            return name

    return ""


async def execute_flow(
    state: FlowExecutionState,
    progress_emitter=None,
) -> FlowExecutionState:
    """
    Ejecuta un Flow completo, lote por lote.
    Si progress_emitter está presente, emite eventos por cada step.
    """
    steps = state["steps"]
    step_outputs = dict(state.get("step_outputs", {}))
    shared_context = dict(state.get("shared_context", {}))
    completed_ids = list(state.get("completed_step_ids", []))

    batches = build_execution_batches(steps)
    total_steps = len(steps)
    step_counter = 0

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

        for result in results:
            if isinstance(result, Exception):
                continue

            step_id = result["step_id"]
            step_outputs[step_id] = result
            completed_ids.append(step_id)

            if result["status"] == "completed" and result.get("content"):
                agent_type = result["agent_type"]
                shared_context[f"step_{agent_type}_result"] = result["content"][:2000]

            if result["status"] == "error":
                state["failed_step_id"] = step_id

        step_counter += len(batch)

    has_errors = any(o.get("status") == "error" for o in step_outputs.values())

    state["step_outputs"] = step_outputs
    state["shared_context"] = shared_context
    state["completed_step_ids"] = completed_ids
    state["completed"] = True
    if has_errors:
        state["error"] = "One or more steps failed during execution"

    return state