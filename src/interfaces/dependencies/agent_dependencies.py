"""
Dependencias de inyección para AgentTask.
AgentConfig ya no existe — los agentes son globales.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.agent_task_sqlalchemy import AgentTaskSQLAlchemyRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.use_cases.execution.agent_task_crud import AgentTaskList


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------

def get_agent_task_repository(session: AsyncSession = Depends(get_session)) -> AgentTaskRepository:
    return AgentTaskSQLAlchemyRepository(session)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------

def get_agent_task_list(task_repo: AgentTaskRepository = Depends(get_agent_task_repository)) -> AgentTaskList:
    return AgentTaskList(task_repo)
