from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.entities.activity_log import ActivityLog
from domain.repositories.activity_log_repository import ActivityLogRepository


class ActivityLogSQLAlchemyRepository(ActivityLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: ActivityLog) -> ActivityLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_by_organization(self, org_id: str, limit: int = 50) -> List[ActivityLog]:
        stmt = select(ActivityLog).where(ActivityLog.organization_id == org_id).order_by(ActivityLog.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())