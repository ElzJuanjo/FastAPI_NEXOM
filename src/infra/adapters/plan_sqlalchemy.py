"""
Implementación SQLAlchemy async del PlanRepository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.plan import Plan
from domain.repositories.plan_repository import PlanRepository


class PlanSQLAlchemyRepository(PlanRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plan_id: str) -> Optional[Plan]:
        stmt = select(Plan).where(Plan.id == plan_id, Plan.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_type(self, plan_type: str) -> Optional[Plan]:
        stmt = select(Plan).where(Plan.plan_type == plan_type, Plan.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Plan]:
        stmt = select(Plan).where(Plan.deleted_at.is_(None)).order_by(Plan.price_monthly_usd)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, plan: Plan) -> Plan:
        self._session.add(plan)
        await self._session.flush()
        return plan