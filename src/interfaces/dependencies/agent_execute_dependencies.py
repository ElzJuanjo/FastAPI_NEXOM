"""
Dependencias de inyección para ejecución de agentes.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.agent_task_sqlalchemy import AgentTaskSQLAlchemyRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.use_cases.agent_execute import AgentExecute


def get_agent_task_repo(session: AsyncSession = Depends(get_session)) -> AgentTaskRepository:
    return AgentTaskSQLAlchemyRepository(session)


def get_agent_execute(
    task_repo: AgentTaskRepository = Depends(get_agent_task_repo),
) -> AgentExecute:
    return AgentExecute(task_repo)
