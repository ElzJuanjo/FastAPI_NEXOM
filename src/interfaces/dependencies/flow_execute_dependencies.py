"""
Dependencias para ejecución de Flows.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.flow_sqlalchemy import FlowSQLAlchemyRepository
from infra.adapters.agent_task_sqlalchemy import AgentTaskSQLAlchemyRepository
from domain.repositories.flow_repository import FlowRepository
from domain.repositories.agent_task_repository import AgentTaskRepository
from app.use_cases.flow.execute import FlowExecute
from app.use_cases.flow.resume import FlowResumeWithSelection


def get_flow_repo(session: AsyncSession = Depends(get_session)) -> FlowRepository:
    return FlowSQLAlchemyRepository(session)


def get_task_repo(session: AsyncSession = Depends(get_session)) -> AgentTaskRepository:
    return AgentTaskSQLAlchemyRepository(session)


def get_flow_execute(
    flow_repo: FlowRepository = Depends(get_flow_repo),
    task_repo: AgentTaskRepository = Depends(get_task_repo),
) -> FlowExecute:
    return FlowExecute(flow_repo, task_repo)


def get_flow_resume(
    flow_repo: FlowRepository = Depends(get_flow_repo),
    task_repo: AgentTaskRepository = Depends(get_task_repo),
) -> FlowResumeWithSelection:
    return FlowResumeWithSelection(flow_repo, task_repo)
