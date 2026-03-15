"""
Estado compartido del orquestador.
TypedDict que LangGraph usa para pasar datos entre nodos del grafo.
"""

from __future__ import annotations

from typing import Optional, Any
from typing_extensions import TypedDict

from langgraph.graph import add_messages


class OrchestratorState(TypedDict):
    """
    Estado mutable que fluye por el grafo del orquestador.

    - messages: historial de conversación (LangGraph lo acumula con add_messages)
    - user_input: la solicitud original del usuario
    - selected_agent: agente elegido por el router
    - agent_output: resultado del agente ejecutado
    - context: datos compartidos entre agentes (brand, product, etc.)
    - flow_id: si estamos dentro de un Flow, su ID
    - current_step: step actual del Flow
    - error: mensaje de error si algo falla
    - completed: flag de finalización
    """
    messages: list  # Annotated con add_messages en el grafo
    user_input: str
    selected_agent: Optional[str]
    agent_output: Optional[dict]
    context: dict
    flow_id: Optional[str]
    current_step: Optional[int]
    error: Optional[str]
    completed: bool