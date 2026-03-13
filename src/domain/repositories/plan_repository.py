"""
Contrato de acceso a datos para Plan.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.plan import Plan


class PlanRepository(ABC):

    @abstractmethod
    async def get_by_id(self, plan_id: str) -> Optional[Plan]:
        ...

    @abstractmethod
    async def get_by_type(self, plan_type: str) -> Optional[Plan]:
        ...

    @abstractmethod
    async def get_all(self) -> List[Plan]:
        ...

    @abstractmethod
    async def create(self, plan: Plan) -> Plan:
        ...