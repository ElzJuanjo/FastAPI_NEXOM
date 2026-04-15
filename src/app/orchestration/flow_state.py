"""
Estado para la ejecución de un Flow multi-agente.
"""

from __future__ import annotations

from typing import Optional, Any
from typing_extensions import TypedDict


class FlowExecutionState(TypedDict, total=False):
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
    - paused: flag que indica que el flow se detuvo esperando input del usuario
        (ej: selección de productos tras product_search)
    - pause_reason: identificador legible de la razón de pausa
    - pause_step_id: ID del step tras el cual se pausó la ejecución
    - pending_candidates: productos candidatos emitidos por el step que pausó
        (solo aplica para product_search); el usuario los elige y se reanuda.
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
    paused: bool
    pause_reason: Optional[str]
    pause_step_id: Optional[str]
    pending_candidates: list[dict]