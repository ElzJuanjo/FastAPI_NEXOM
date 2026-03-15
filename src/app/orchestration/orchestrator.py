"""
Orquestador principal de NexOS — LangGraph StateGraph.

Nivel 1: Router decide → Executor ejecuta → Response
Nivel 2: Cada agente puede tener su propio sub-grafo interno (futuro)
Nivel 3: Flows multi-agente con ejecución secuencial/paralela (Sprint 11C)
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import OrchestratorState
from .router_node import router_node
from .executor_node import executor_node


def should_execute(state: OrchestratorState) -> str:
    """Condicional: si el router encontró un agente, ejecutar. Si no, terminar."""
    if state.get("error"):
        return "end"
    if state.get("selected_agent") and state["selected_agent"] != "none":
        return "execute"
    return "end"


def build_orchestrator() -> StateGraph:
    """
    Construye el grafo del orquestador.

    Flujo:
    START → router → (¿hay agente?) → executor → END
                                    → END (si no hay agente)
    """
    graph = StateGraph(OrchestratorState)

    # Agregar nodos
    graph.add_node("router", router_node)
    graph.add_node("executor", executor_node)

    # Flujo: START → router
    graph.add_edge(START, "router")

    # Condicional: router → executor o → END
    graph.add_conditional_edges(
        "router",
        should_execute,
        {
            "execute": "executor",
            "end": END,
        },
    )

    # executor → END
    graph.add_edge("executor", END)

    return graph


# Compilar el grafo una sola vez (singleton)
orchestrator_graph = build_orchestrator().compile()


async def run_orchestrator(
    user_input: str,
    context: dict | None = None,
) -> dict:
    """
    Ejecuta el orquestador completo.

    Args:
        user_input: solicitud del usuario
        context: datos adicionales (market, brand_id, etc.)

    Returns:
        Dict con: content, selected_agent, reasoning, tokens, etc.
    """
    initial_state = {
        "messages": [],
        "user_input": user_input,
        "selected_agent": None,
        "agent_output": None,
        "context": context or {},
        "flow_id": None,
        "current_step": None,
        "error": None,
        "completed": False,
    }

    # Ejecutar el grafo
    final_state = await orchestrator_graph.ainvoke(initial_state)

    # Construir respuesta
    agent_output = final_state.get("agent_output") or {}
    router_reasoning = final_state.get("context", {}).get("_router_reasoning", "")

    return {
        "content": agent_output.get("content", final_state.get("error", "Sin respuesta")),
        "selected_agent": final_state.get("selected_agent"),
        "router_reasoning": router_reasoning,
        "model": agent_output.get("model"),
        "tokens_used": agent_output.get("tokens_total", 0),
        "scraped_sources": agent_output.get("scraped_sources"),
        "dropi_data": agent_output.get("dropi_data"),
        "error": final_state.get("error"),
    }