"""
Contrato de acceso a datos para AgentConfig.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.agent import AgentConfig


class AgentConfigRepository(ABC):

    @abstractmethod
    async def get_by_id(self, config_id: str) -> Optional[AgentConfig]:
        ...

    @abstractmethod
    async def get_by_org_and_type(self, org_id: str, agent_type: str) -> Optional[AgentConfig]:
        ...

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> List[AgentConfig]:
        ...

    @abstractmethod
    async def create(self, config: AgentConfig) -> AgentConfig:
        ...

    @abstractmethod
    async def update(self, config: AgentConfig) -> AgentConfig:
        ...