"""
Nodo Router — un LLM decide qué agente debe responder.
Recibe historial conversacional para decisiones contextuales inteligentes.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from infra.config.llm_factory import get_chat_model
from .state import OrchestratorState


ROUTER_SYSTEM_PROMPT = """You are the intelligent orchestrator of NEXOM, an AI-powered E-Commerce automation platform.

Your ONLY job is to analyze the user's request (considering conversation history) and decide which specialized agent should respond.

AVAILABLE AGENTS:
- general_assistant: Greetings, general questions, guiding the user, explaining capabilities, ambiguous requests.
- product_search: Search products in the market, analyze niches, trends, prices. Real data from MercadoLibre, Google Shopping, AliExpress, Amazon, Temu.
- dropi_connector: Search/sync products in Dropi, check stock, supplier prices, dropshipping operations.
- branding: Create brand identity (name, logo, color palette, typography, tone, key messages, brand book).
- copywriting: Generate sales copy (headlines, descriptions, emails, ads, CTAs, social posts, scripts).
- ads: Create ad campaigns for Meta Ads, Google Ads, TikTok Ads.
- landing_page: Design and generate high-conversion sales landing pages.
- image_gen: Generate product images, visual creatives for ads.
- store_dev: Develop and configure online stores.
- conversion_opt: Analyze conversion metrics and recommend optimizations (AOV, CLTV, CRO, funnel).

DECISION RULES (in strict priority order):

1. GRATITUDE AND CLOSURES: If the message is a simple thank you, farewell, or acknowledgment ("thanks", "gracias", "thank you", "muchas gracias", "ok gracias", "perfecto gracias", "genial", "excelente", "great", "awesome", "bye", "chao", "adiós", "goodbye", "listo", "👍"), ALWAYS route to general_assistant. These are social messages, not task requests.

2. NUMBERED OPTION SELECTION: If the user responds with ONLY a number ("1", "2", "3") or ordinal ("the first", "the second", "el primero", "la segunda", "la tercera"), the user is selecting from a numbered list in the LAST assistant message. You MUST read that list, identify what each option refers to, and route to the matching agent:
   - Option mentions copy/headlines/descriptions/emails/textos/anuncios escritos → copywriting
   - Option mentions ads/campaign/Meta Ads/Google Ads/TikTok/creativos para ads → ads
   - Option mentions landing page/página de venta/conversión alta → landing_page
   - Option mentions store/tienda/Shopify/Dropi integration/configurar → store_dev
   - Option mentions brand/marca/identidad/brand book/logo/colores → branding
   - Option mentions image/imagen/foto/creativo visual/imágenes → image_gen
   - Option mentions product search/productos ganadores/búsqueda/mercado/nicho → product_search
   - Option mentions Dropi/sync/stock/dropshipping/proveedor → dropi_connector
   - Option mentions conversion/métricas/AOV/CRO/optimización → conversion_opt
   A number response is ALWAYS an option selection from the previous message. NEVER treat it as a generic continuation.

3. CONVERSATION CONTEXT IS KING: If the history shows the user was working on a specific topic and the new message is a continuation ("yes", "let's go", "continue", "do it", "sí", "dale", "continuemos", "hazlo", "sigue", "continúa", "continue generating", "keep going", "pick up where you left off"), use the agent from the active topic. NEVER fall back to general_assistant for continuations.

4. NATURAL TRANSITIONS: If the assistant suggested a next step and the user accepts it (not by number, but by describing it), switch to the corresponding agent:
   - Brand book / brand identity / logo / colors → branding
   - Generate images / creatives / visual content → image_gen
   - Sync with Dropi / dropshipping / supplier → dropi_connector
   - Write copy / texts / email / headlines → copywriting
   - Ad campaign / Meta Ads / Google Ads / budget → ads
   - Landing page / sales page → landing_page
   - Configure store / online store → store_dev
   - Conversion analysis / metrics / AOV / funnel → conversion_opt
   - Search products / market / niche / winning products → product_search

5. EXPLICIT INTENT: If the message clearly and directly mentions a domain keyword, that agent wins regardless of history.

6. GENERAL_ASSISTANT ONLY WHEN: It's an initial greeting with no history, a question about NEXOM capabilities, or there is genuinely no prior context and no clear intent. Use general_assistant as an absolute LAST resort.

7. LANGUAGE IS IRRELEVANT: The user may write in Spanish, English, Portuguese, or any language. Route based on intent, never on language.

Respond ONLY with valid JSON, no markdown, no explanation:
{"agent": "agent_name", "reasoning": "brief reason max 20 words"}
"""


async def router_node(state: OrchestratorState) -> dict:
    """
    Analiza el input del usuario CON historial conversacional y decide qué agente usar.
    """
    # If agent was forced, skip routing
    if state.get("selected_agent"):
        selected = state["selected_agent"]
        emitter = state.get("context", {}).get("_progress_emitter")
        if emitter:
            await emitter.emit("executing", 25, agent=selected, message=f"Using {selected} (forced)...")
        return {
            "selected_agent": selected,
            "context": {**state.get("context", {}), "_router_reasoning": f"Forced agent: {selected}"},
        }
        
    llm = get_chat_model()

    # Construir contexto con historial (últimos 12 mensajes)
    conversation_history = state.get("context", {}).get("conversation_history", [])
    history_text = ""
    if conversation_history:
        recent = conversation_history[-12:]
        history_parts = []

        # Find the last assistant message index
        last_assistant_idx = -1
        for i in range(len(recent) - 1, -1, -1):
            if recent[i].get("role") == "assistant":
                last_assistant_idx = i
                break

        for i, msg in enumerate(recent):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Last assistant message gets more space (critical for numbered option detection)
            max_len = 1500 if i == last_assistant_idx else 500
            if len(content) > max_len:
                content = content[:max_len] + "..."
            history_parts.append(f"[{role}]: {content}")

        history_text = "\n".join(history_parts)

    # Construir prompt
    router_input = f"Current user message: {state['user_input']}"
    if history_text:
        router_input = f"CONVERSATION HISTORY:\n{history_text}\n\n---\n\n{router_input}"
        
    input_images = state.get("context", {}).get("input_images", [])
    if input_images:
        router_input += f"\n\n[USER ATTACHED {len(input_images)} IMAGE(S)]"
        # Si no hay texto, la intención más probable es búsqueda visual o referencia para creativo
        if not state["user_input"].strip():
            router_input += "\nNote: No text was provided, only image(s). Default to product_search for visual search, or image_gen if context suggests creative work."

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=router_input),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    try:
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        decision = json.loads(content)
        selected = decision.get("agent", "general_assistant")
        reasoning = decision.get("reasoning", "")
        
        # Emit progress
        emitter = state.get("context", {}).get("_progress_emitter")
        if emitter:
            await emitter.emit("executing", 25, agent=selected, message=f"Routing to {selected}...")

        return {
            "selected_agent": selected,
            "context": {
                **state.get("context", {}),
                "_router_reasoning": reasoning,
            },
        }

    except (json.JSONDecodeError, KeyError):
        return {
            "selected_agent": "general_assistant",
            "context": {
                **state.get("context", {}),
                "_router_reasoning": f"Error parsing, fallback: {content[:100]}",
            },
        }
