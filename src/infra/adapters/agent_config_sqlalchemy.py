"""
Implementación SQLAlchemy async del AgentConfigRepository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.agent import AgentConfig
from domain.repositories.agent_config_repository import AgentConfigRepository


class AgentConfigSQLAlchemyRepository(AgentConfigRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, config_id: str) -> Optional[AgentConfig]:
        stmt = select(AgentConfig).where(
            AgentConfig.id == config_id,
            AgentConfig.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_org_and_type(self, org_id: str, agent_type: str) -> Optional[AgentConfig]:
        stmt = select(AgentConfig).where(
            AgentConfig.organization_id == org_id,
            AgentConfig.agent_type == agent_type,
            AgentConfig.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: str) -> List[AgentConfig]:
        stmt = (
            select(AgentConfig)
            .where(AgentConfig.organization_id == org_id, AgentConfig.deleted_at.is_(None))
            .order_by(AgentConfig.agent_type)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, config: AgentConfig) -> AgentConfig:
        self._session.add(config)
        await self._session.flush()
        return config

    async def update(self, config: AgentConfig) -> AgentConfig:
        await self._session.flush()
        return config