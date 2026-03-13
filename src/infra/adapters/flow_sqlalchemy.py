"""
Implementación SQLAlchemy async del FlowRepository.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.flow import Flow, FlowStep
from domain.repositories.flow_repository import FlowRepository


class FlowSQLAlchemyRepository(FlowRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, flow_id: str) -> Optional[Flow]:
        stmt = (
            select(Flow)
            .options(selectinload(Flow.steps))
            .where(Flow.id == flow_id, Flow.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: str) -> List[Flow]:
        stmt = (
            select(Flow)
            .options(selectinload(Flow.steps))
            .where(Flow.organization_id == org_id, Flow.deleted_at.is_(None))
            .order_by(Flow.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, flow: Flow) -> Flow:
        self._session.add(flow)
        await self._session.flush()
        return flow

    async def update(self, flow: Flow) -> Flow:
        await self._session.flush()
        return flow

    async def soft_delete(self, flow_id: str) -> None:
        stmt = select(Flow).where(Flow.id == flow_id, Flow.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        flow = result.scalar_one_or_none()
        if flow:
            flow.deleted_at = datetime.now(timezone.utc)
            await self._session.flush()

    async def add_step(self, step: FlowStep) -> FlowStep:
        self._session.add(step)
        await self._session.flush()
        return step

    async def get_step_by_id(self, step_id: str) -> Optional[FlowStep]:
        stmt = select(FlowStep).where(FlowStep.id == step_id, FlowStep.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_step(self, step: FlowStep) -> FlowStep:
        await self._session.flush()
        return step