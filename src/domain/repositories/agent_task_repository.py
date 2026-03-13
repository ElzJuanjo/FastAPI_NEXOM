"""
Contrato de acceso a datos para AgentTask.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.agent import AgentTask


class AgentTaskRepository(ABC):

    @abstractmethod
    async def get_by_id(self, task_id: str) -> Optional[AgentTask]:
        ...

    @abstractmethod
    async def list_by_config(self, config_id: str, limit: int = 20) -> List[AgentTask]:
        ...

    @abstractmethod
    async def create(self, task: AgentTask) -> AgentTask:
        ...

    @abstractmethod
    async def update(self, task: AgentTask) -> AgentTask:
        ...