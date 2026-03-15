"""
Nodo Router — un LLM decide qué agente debe responder.
Es el cerebro del Nivel 1.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from infra.config.llm_factory import get_chat_model
from app.agents.agent_registry import list_available_agents
from .state import OrchestratorState


ROUTER_SYSTEM_PROMPT = """Eres el orquestador de NexOS, una plataforma de E-Commerce con IA.

Tu ÚNICO trabajo es decidir qué agente debe manejar la solicitud del usuario.

Agentes disponibles:
- general_assistant: Para saludos, preguntas generales, solicitudes ambiguas, o cuando el usuario no tiene claro qué quiere hacer. SIEMPRE usa este agente si la solicitud es vaga, es un saludo, o no encaja claramente con otro agente.
- product_search: Buscar productos en el mercado, analizar nichos, tendencias, precios. Usa datos reales de MercadoLibre, Google Shopping, AliExpress, Amazon, Temu.
- dropi_connector: Buscar productos en el catálogo de Dropi, consultar stock, precios de proveedor, crear órdenes de dropshipping.
- branding: Crear identidad de marca (nombre, logo, paleta de colores, tipografía, tono de voz, mensajes clave).
- copywriting: Generar textos de venta (headlines, descripciones, emails, anuncios, CTAs).
- ads: Crear campañas de anuncios para Meta Ads, Google Ads, TikTok Ads.
- landing_page: Diseñar y generar landing pages de venta.
- image_gen: Generar imágenes de producto, creativos visuales para anuncios.
- video_gen: Generar videos de producto, reels, contenido para redes.
- store_dev: Desarrollar y configurar tienda online.
- conversion_opt: Analizar métricas de conversión y recomendar optimizaciones.

REGLAS DE DECISIÓN:
1. Si es un saludo, pregunta general o solicitud ambigua → general_assistant
2. Si el usuario menciona explícitamente buscar/encontrar productos en el mercado → product_search
3. Si menciona Dropi, dropshipping, catálogo de proveedor → dropi_connector
4. Si menciona marca, identidad, logo, colores → branding
5. Si menciona textos, copy, headlines, anuncios escritos → copywriting
6. Si menciona campaña de anuncios, Meta Ads, Google Ads → ads
7. Si menciona landing page, página de venta → landing_page
8. Si menciona imagen, foto, creativo visual → image_gen
9. Si menciona video, reel → video_gen
10. Si menciona tienda, store, configurar tienda → store_dev
11. Si menciona conversión, métricas, AOV, abandono → conversion_opt
12. Si la solicitud necesita MÚLTIPLES agentes, indica cuáles.

Responde SOLO con un JSON válido, sin markdown ni explicación:
{"agent": "nombre_del_agente", "reasoning": "razón breve"}

Si la solicitud necesita MÚLTIPLES agentes en secuencia:
{"agent": "multi", "agents": ["agente1", "agente2"], "reasoning": "razón"}
"""


async def router_node(state: OrchestratorState) -> dict:
    """
    Analiza el input del usuario y decide qué agente debe responder.
    Retorna el estado actualizado con selected_agent.
    """
    llm = get_chat_model(model="openai/gpt-4o-mini", temperature=0.1, max_tokens=200)

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=f"Solicitud del usuario: {state['user_input']}\n\nContexto adicional: {json.dumps(state.get('context', {}), ensure_ascii=False)}"),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # Parsear respuesta JSON del router
    try:
        # Limpiar posibles backticks markdown
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        decision = json.loads(content)
        selected = decision.get("agent", "none")
        reasoning = decision.get("reasoning", "")

        if selected == "multi":
            # Para multi-agente, tomamos el primero y guardamos la lista
            agents_list = decision.get("agents", [])
            return {
                "selected_agent": agents_list[0] if agents_list else "none",
                "context": {
                    **state.get("context", {}),
                    "_router_reasoning": reasoning,
                    "_planned_agents": agents_list,
                },
            }

        return {
            "selected_agent": selected,
            "context": {
                **state.get("context", {}),
                "_router_reasoning": reasoning,
            },
        }

    except (json.JSONDecodeError, KeyError):
        return {
            "selected_agent": "none",
            "error": f"Router no pudo parsear la decisión: {content}",
        }