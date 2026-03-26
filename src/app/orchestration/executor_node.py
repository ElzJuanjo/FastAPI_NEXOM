"""
Nodo Executor — ejecuta el agente seleccionado por el router.
Pasa el historial conversacional al agente para que tenga contexto.
"""

from __future__ import annotations

from app.agents.agent_registry import get_agent
from .state import OrchestratorState


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
        # Pasar contexto incluyendo historial conversacional
        full_context = state.get("context", {})

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

        # Emit progress
        emitter = full_context.get("_progress_emitter")
        if emitter:
            await emitter.emit("generating", 40, agent=agent_type, message=f"Agent {agent_type} processing...")
            
        result = await agent.execute(
            user_input=state["user_input"],
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