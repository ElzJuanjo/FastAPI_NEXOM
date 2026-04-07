"""
Endpoints de AgentTask y listado de agentes disponibles.
Los agentes son globales — no se configuran per-org.
"""

from fastapi import APIRouter, Depends, Query, status

from app.dto.agent_dto import AgentTaskResponse, AgentTaskListResponse
from app.use_cases.execution.agent_task_crud import AgentTaskList
from interfaces.dependencies.agent_dependencies import get_agent_task_list
from interfaces.dependencies.auth_dependencies import get_current_user_id
from interfaces.dependencies.org_membership import get_current_org_id
from app.agents.agent_registry import list_available_agents
from app.agents.credit_costs import CREDIT_COSTS


# ===========================================================================
# Agentes disponibles (globales)
# ===========================================================================

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


@agents_router.get("/available")
async def get_available_agents(
    user_id: str = Depends(get_current_user_id),
):
    """
    Lista todos los agentes disponibles en el sistema con su costo en créditos.
    Los agentes son globales — no requieren configuración per-org.
    """
    available = list_available_agents()
    return {
        "agents": [
            {
                "agent_type": agent_type,
                "credits_per_use": CREDIT_COSTS.get(agent_type, 5),
            }
            for agent_type in available
        ],
    }


# ===========================================================================
# Agent Tasks (historial de ejecuciones)
# ===========================================================================

task_router = APIRouter(prefix="/agent-tasks", tags=["Agent Tasks"])


@task_router.get("", response_model=AgentTaskListResponse)
async def list_agent_tasks(
    agent_type: str | None = Query(default=None, description="Filtrar por tipo de agente"),
    limit: int = Query(default=20, le=100),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    use_case: AgentTaskList = Depends(get_agent_task_list),
):
    """Lista el historial de ejecuciones de agentes de tu organización."""
    tasks = await use_case.execute(org_id, agent_type=agent_type, limit=limit)
    return AgentTaskListResponse(
        tasks=[AgentTaskResponse.model_validate(t) for t in tasks]
    )
