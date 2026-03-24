"""
Ejecutor de Flows — corre los steps de un Flow en orden,
respetando dependencias y soportando ejecución paralela por lote.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.agent_registry import get_agent
from .flow_state import FlowExecutionState
from .flow_planner import build_execution_batches, get_step_context


async def execute_single_step(
    step: dict,
    step_outputs: dict[str, dict],
    shared_context: dict,
) -> dict:
    """
    Ejecuta un step individual invocando su agente.

    Returns:
        Dict con: step_id, agent_type, status, content, tokens, duration, error
    """
    step_id = step["id"]
    agent_type = step["agent_type"]
    step_name = step.get("name", agent_type)
    started_at = datetime.now(timezone.utc)

    agent = get_agent(agent_type)

    if not agent:
        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "error",
            "content": f"Agent '{agent_type}' not available",
            "tokens_total": 0,
            "duration_ms": 0,
            "error": f"Agent '{agent_type}' not registered in the system",
        }

    try:
        # Construir contexto enriquecido con outputs previos
        context = get_step_context(step, step_outputs, shared_context)

        # El input para el agente es el nombre del step + contexto
        user_input = f"Ejecuta la tarea: {step_name}"

        result = await agent.execute(
            user_input=user_input,
            context=context,
        )

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "completed",
            "content": result.get("content", ""),
            "model": result.get("model"),
            "tokens_total": result.get("tokens_total", 0),
            "duration_ms": duration_ms,
            "error": None,
            "scraped_sources": result.get("scraped_sources"),
            "dropi_data": result.get("dropi_data"),
        }

    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        return {
            "step_id": step_id,
            "agent_type": agent_type,
            "status": "error",
            "content": None,
            "tokens_total": 0,
            "duration_ms": duration_ms,
            "error": str(e),
        }


async def execute_flow(state: FlowExecutionState) -> FlowExecutionState:
    """
    Ejecuta un Flow completo, lote por lote.

    - Cada lote contiene steps que pueden correr en paralelo.
    - El output de cada step se acumula en step_outputs y shared_context.
    - Si un step falla, el Flow se marca con error pero continúa
      los steps que no dependen del fallido.
    """
    steps = state["steps"]
    step_outputs = dict(state.get("step_outputs", {}))
    shared_context = dict(state.get("shared_context", {}))
    completed_ids = list(state.get("completed_step_ids", []))

    # Generar lotes de ejecución
    batches = build_execution_batches(steps)

    total_steps = len(steps)
    completed_count = 0

    for batch_idx, batch in enumerate(batches):
        # Ejecutar todos los steps del lote en paralelo
        tasks = [
            execute_single_step(step, step_outputs, shared_context)
            for step in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # asyncio.gather con return_exceptions=True
                continue

            step_id = result["step_id"]
            step_outputs[step_id] = result
            completed_ids.append(step_id)
            completed_count += 1

            # Enriquecer shared_context con el output de este step
            if result["status"] == "completed" and result.get("content"):
                agent_type = result["agent_type"]
                shared_context[f"step_{agent_type}_result"] = result["content"][:2000]

            # Si falló, marcar
            if result["status"] == "error":
                state["failed_step_id"] = step_id

    # Determinar estado final
    has_errors = any(
        o.get("status") == "error" for o in step_outputs.values()
    )

    state["step_outputs"] = step_outputs
    state["shared_context"] = shared_context
    state["completed_step_ids"] = completed_ids
    state["completed"] = True
    if has_errors:
        state["error"] = "One or more steps failed during execution"

    return state