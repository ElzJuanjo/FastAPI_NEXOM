"""
Planificador de ejecución de Flows.
Analiza dependencias entre steps y genera lotes de ejecución
(secuencial o paralelo según depends_on_step_id).
"""

from __future__ import annotations


def build_execution_batches(steps: list[dict]) -> list[list[dict]]:
    """
    Dado una lista de steps con sus dependencias, genera lotes de ejecución.
    Steps sin dependencias pendientes van en el mismo lote (paralelo).
    Steps con dependencias esperan a que su lote previo termine.

    Args:
        steps: lista de dicts con keys: id, order, depends_on_step_id, agent_type, name

    Returns:
        Lista de lotes. Cada lote es una lista de steps que pueden correr en paralelo.

    Ejemplo:
        Step 1: sin deps        → Lote 1: [Step 1]
        Step 2: depende de 1    → Lote 2: [Step 2]
        Step 3: depende de 1    → Lote 2: [Step 2, Step 3]  (paralelo)
        Step 4: depende de 2,3  → Lote 3: [Step 4]
    """
    if not steps:
        return []

    # Indexar por ID
    step_map = {s["id"]: s for s in steps}
    completed = set()
    batches = []
    remaining = set(s["id"] for s in steps)

    # Safety: máximo de iteraciones para evitar loops infinitos
    max_iterations = len(steps) + 1
    iteration = 0

    while remaining and iteration < max_iterations:
        iteration += 1
        batch = []

        for step_id in list(remaining):
            step = step_map[step_id]
            dep_id = step.get("depends_on_step_id")

            # Sin dependencia, o dependencia ya completada → listo para ejecutar
            if dep_id is None or dep_id in completed:
                batch.append(step)

        if not batch:
            # Dependencia circular o step apuntando a step inexistente
            # Forzar ejecución del step con menor order
            fallback = min(remaining, key=lambda sid: step_map[sid]["order"])
            batch = [step_map[fallback]]

        batches.append(batch)

        for s in batch:
            completed.add(s["id"])
            remaining.discard(s["id"])

    return batches


def get_step_context(
    step: dict,
    step_outputs: dict[str, dict],
    shared_context: dict,
) -> dict:
    """
    Construye el contexto para un step basándose en:
    - El contexto compartido del Flow
    - Los outputs de los steps de los que depende
    """
    context = {**shared_context}

    # Agregar output del step del que depende directamente
    dep_id = step.get("depends_on_step_id")
    if dep_id and dep_id in step_outputs:
        dep_output = step_outputs[dep_id]
        context[f"previous_step_output"] = dep_output.get("content", "")
        context[f"previous_step_agent"] = dep_output.get("agent_type", "")

    # Agregar todos los outputs previos como referencia
    for sid, output in step_outputs.items():
        agent_type = output.get("agent_type", "unknown")
        context[f"step_{agent_type}_output"] = output.get("content", "")

    return context