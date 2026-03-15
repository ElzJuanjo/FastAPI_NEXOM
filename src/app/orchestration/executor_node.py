"""
Nodo Executor — ejecuta el agente seleccionado por el router.
Usa los agentes existentes (BaseAgent subclasses) del registry.
"""

from __future__ import annotations

from app.agents.agent_registry import get_agent
from .state import OrchestratorState


async def executor_node(state: OrchestratorState) -> dict:
    """
    Ejecuta el agente seleccionado y retorna el resultado.
    """
    agent_type = state.get("selected_agent")

    if not agent_type or agent_type == "none":
        return {
            "agent_output": {
                "content": "No se identificó un agente adecuado para tu solicitud. ¿Puedes ser más específico?",
                "model": "none",
                "tokens_total": 0,
            },
            "completed": True,
        }

    agent = get_agent(agent_type)

    if not agent:
        return {
            "agent_output": {
                "content": f"El agente '{agent_type}' aún no está disponible. Los agentes activos son: product_search, dropi_connector.",
                "model": "none",
                "tokens_total": 0,
            },
            "completed": True,
        }

    try:
        # Filtrar keys internas del contexto para el agente
        user_context = {
            k: v for k, v in state.get("context", {}).items()
            if not k.startswith("_")
        }

        result = await agent.execute(
            user_input=state["user_input"],
            context=user_context if user_context else None,
        )

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