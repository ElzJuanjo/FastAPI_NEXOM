"""
Orquestador principal de NexOS — LangGraph StateGraph.
El router LLM decide qué agente usar basándose en el mensaje + historial.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import OrchestratorState
from .router_node import router_node
from .executor_node import executor_node


def should_execute(state: OrchestratorState) -> str:
    if state.get("error"):
        return "end"
    if state.get("selected_agent") and state["selected_agent"] != "none":
        return "execute"
    return "end"


def build_orchestrator() -> StateGraph:
    graph = StateGraph(OrchestratorState)
    graph.add_node("router", router_node)
    graph.add_node("executor", executor_node)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        should_execute,
        {"execute": "executor", "end": END},
    )
    graph.add_edge("executor", END)
    return graph


orchestrator_graph = build_orchestrator().compile()


async def run_orchestrator(
    user_input: str,
    context: dict | None = None,
) -> dict:
    """
    Ejecuta el orquestador completo.
    El router LLM decide el agente basándose en el mensaje y el historial conversacional.
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

    final_state = await orchestrator_graph.ainvoke(initial_state)

    agent_output = final_state.get("agent_output") or {}
    router_reasoning = final_state.get("context", {}).get("_router_reasoning", "")

    return {
        "content": agent_output.get("content", final_state.get("error", "No response generated. / Sin respuesta generada.")),
        "selected_agent": final_state.get("selected_agent"),
        "router_reasoning": router_reasoning,
        "model": agent_output.get("model"),
        "tokens_used": agent_output.get("tokens_total", 0),
        "scraped_sources": agent_output.get("scraped_sources"),
        "dropi_data": agent_output.get("dropi_data"),
        "images": agent_output.get("images"),
        "image_count": agent_output.get("image_count"),
        "error": final_state.get("error"),
    }