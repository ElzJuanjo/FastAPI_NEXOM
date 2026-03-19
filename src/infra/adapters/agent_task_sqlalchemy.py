"""
Implementación SQLAlchemy async del AgentTaskRepository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.agent import AgentTask
from domain.repositories.agent_task_repository import AgentTaskRepository


class AgentTaskSQLAlchemyRepository(AgentTaskRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: str) -> Optional[AgentTask]:
        stmt = select(AgentTask).where(AgentTask.id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: str, limit: int = 20) -> List[AgentTask]:
        stmt = (
            select(AgentTask)
            .where(AgentTask.organization_id == org_id)
            .order_by(AgentTask.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_org_and_type(self, org_id: str, agent_type: str, limit: int = 20) -> List[AgentTask]:
        stmt = (
            select(AgentTask)
            .where(
                AgentTask.organization_id == org_id,
                AgentTask.agent_type == agent_type,
            )
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
