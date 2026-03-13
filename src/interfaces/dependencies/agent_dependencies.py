"""
Dependencias de inyección para AgentConfig y AgentTask.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.agent_config_sqlalchemy import AgentConfigSQLAlchemyRepository
from infra.adapters.agent_task_sqlalchemy import AgentTaskSQLAlchemyRepository
from domain.repositories.agent_config_repository import AgentConfigRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.use_cases.agent_config_crud import AgentConfigCreate, AgentConfigList, AgentConfigUpdate
from app.use_cases.agent_task_crud import AgentTaskCreate, AgentTaskList


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------

def get_agent_config_repository(session: AsyncSession = Depends(get_session)) -> AgentConfigRepository:
    return AgentConfigSQLAlchemyRepository(session)


def get_agent_task_repository(session: AsyncSession = Depends(get_session)) -> AgentTaskRepository:
    return AgentTaskSQLAlchemyRepository(session)


# ---------------------------------------------------------------------------
# Use cases - AgentConfig
# ---------------------------------------------------------------------------

def get_agent_config_create(repo: AgentConfigRepository = Depends(get_agent_config_repository)) -> AgentConfigCreate:
    return AgentConfigCreate(repo)


def get_agent_config_list(repo: AgentConfigRepository = Depends(get_agent_config_repository)) -> AgentConfigList:
    return AgentConfigList(repo)


def get_agent_config_update(repo: AgentConfigRepository = Depends(get_agent_config_repository)) -> AgentConfigUpdate:
    return AgentConfigUpdate(repo)


# ---------------------------------------------------------------------------
# Use cases - AgentTask
# ---------------------------------------------------------------------------

def get_agent_task_create(
    task_repo: AgentTaskRepository = Depends(get_agent_task_repository),
    config_repo: AgentConfigRepository = Depends(get_agent_config_repository),
) -> AgentTaskCreate:
    return AgentTaskCreate(task_repo, config_repo)


def get_agent_task_list(task_repo: AgentTaskRepository = Depends(get_agent_task_repository)) -> AgentTaskList:
    return AgentTaskList(task_repo)