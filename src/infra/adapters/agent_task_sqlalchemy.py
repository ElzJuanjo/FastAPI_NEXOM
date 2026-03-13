"""
Implementación SQLAlchemy async del AgentTaskRepository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.agent import AgentTask
from domain.repositories.agent_task_repository import AgentTaskRepository


class AgentTaskSQLAlchemyRepository(AgentTaskRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: str) -> Optional[AgentTask]:
        stmt = (
            select(AgentTask)
            .options(selectinload(AgentTask.agent_config))
            .where(AgentTask.id == task_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_config(self, config_id: str, limit: int = 20) -> List[AgentTask]:
        stmt = (
            select(AgentTask)
            .where(AgentTask.agent_config_id == config_id)
            .order_by(AgentTask.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, task: AgentTask) -> AgentTask:
        self._session.add(task)
        await self._session.flush()
        return task

    async def update(self, task: AgentTask) -> AgentTask:
        await self._session.flush()
        return task