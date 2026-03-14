from abc import ABC, abstractmethod
from typing import List
from domain.entities.activity_log import ActivityLog


class ActivityLogRepository(ABC):
    @abstractmethod
    async def create(self, log: ActivityLog) -> ActivityLog: ...
    @abstractmethod
    async def list_by_organization(self, org_id: str, limit: int = 50) -> List[ActivityLog]: ...