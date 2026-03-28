"""
Contrato de acceso a datos para Flow y FlowStep.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.flow import Flow, FlowStep


class FlowRepository(ABC):

    @abstractmethod
    async def get_by_id(self, flow_id: str) -> Optional[Flow]:
        ...

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> List[Flow]:
        ...

    @abstractmethod
    async def create(self, flow: Flow) -> Flow:
        ...

    @abstractmethod
    async def update(self, flow: Flow) -> Flow:
        ...

    @abstractmethod
    async def delete(self, flow: Flow) -> None:
        ...

    @abstractmethod
    async def add_step(self, step: FlowStep) -> FlowStep:
        ...

    @abstractmethod
    async def get_step_by_id(self, step_id: str) -> Optional[FlowStep]:
        ...

    @abstractmethod
    async def update_step(self, step: FlowStep) -> FlowStep:
        ...
        
    @abstractmethod
    async def clear_step_dependencies(self, flow_id: str) -> None:
        ...