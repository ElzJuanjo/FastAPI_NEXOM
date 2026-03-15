"""
Estado para la ejecución de un Flow multi-agente.
"""

from __future__ import annotations

from typing import Optional, Any
from typing_extensions import TypedDict


class FlowExecutionState(TypedDict):
    """
    Estado mutable que fluye por el grafo de ejecución de un Flow.

    - flow_id: ID del Flow en la BD
    - organization_id: org dueña del Flow
    - steps: lista de steps con su config y estado de ejecución
    - step_outputs: dict {step_id: output} acumulando resultados
    - shared_context: contexto compartido que crece con cada step
    - current_step_ids: step(s) que se están ejecutando ahora
    - completed_step_ids: steps que ya terminaron
    - failed_step_id: si un step falló, su ID
    - error: mensaje de error global
    - completed: flag de finalización del Flow completo
    """
    flow_id: str
    organization_id: str
    steps: list[dict]
    step_outputs: dict[str, dict]
    shared_context: dict
    current_step_ids: list[str]
    completed_step_ids: list[str]
    failed_step_id: Optional[str]
    error: Optional[str]
    completed: bool