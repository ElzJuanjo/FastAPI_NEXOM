"""
Casos de uso para Flow y FlowStep.
"""

from datetime import datetime, timezone
from typing import List, Optional

from domain.entities.flow import Flow, FlowStep
from domain.entities.base import FlowStatus, StepStatus
from domain.repositories.flow_repository import FlowRepository


class FlowNotFoundError(Exception):
    pass


class FlowStepNotFoundError(Exception):
    pass


class FlowCreate:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(
        self,
        org_id: str,
        name: str,
        context: dict | None = None,
        steps_data: list[dict] | None = None,
    ) -> Flow:
        flow = Flow(
            organization_id=org_id,
            name=name,
            status=FlowStatus.INACTIVE,
            context=context,
        )
        flow = await self._flow_repo.create(flow)

        if steps_data:
            for step_data in steps_data:
                step = FlowStep(
                    flow_id=flow.id,
                    agent_type=step_data["agent_type"],
                    name=step_data["name"],
                    order=step_data["order"],
                    status=StepStatus.PENDING,
                    depends_on_step_id=step_data.get("depends_on_step_id"),
                )
                await self._flow_repo.add_step(step)

        return flow


class FlowList:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(self, org_id: str) -> List[Flow]:
        return await self._flow_repo.list_by_organization(org_id)


class FlowUpdate:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(self, flow_id: str, **kwargs) -> Flow:
        flow = await self._flow_repo.get_by_id(flow_id)
        if not flow:
            raise FlowNotFoundError(f"Flow {flow_id} no encontrado")

        for key, value in kwargs.items():
            if value is not None:
                setattr(flow, key, value)

        # Si se cambia a RUNNING, registrar started_at
        if kwargs.get("status") == FlowStatus.RUNNING and not flow.started_at:
            flow.started_at = datetime.now(timezone.utc)

        # Si se cambia a COMPLETED, registrar completed_at
        if kwargs.get("status") == FlowStatus.COMPLETED and not flow.completed_at:
            flow.completed_at = datetime.now(timezone.utc)

        return await self._flow_repo.update(flow)


class FlowDelete:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(self, flow_id: str) -> None:
        flow = await self._flow_repo.get_by_id(flow_id)
        if not flow:
            raise FlowNotFoundError(f"Flow {flow_id} no encontrado")
        await self._flow_repo.soft_delete(flow_id)


class FlowStepUpdate:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(self, step_id: str, **kwargs) -> FlowStep:
        step = await self._flow_repo.get_step_by_id(step_id)
        if not step:
            raise FlowStepNotFoundError(f"FlowStep {step_id} no encontrado")

        for key, value in kwargs.items():
            if value is not None:
                setattr(step, key, value)

        if kwargs.get("status") == StepStatus.IN_PROGRESS and not step.started_at:
            step.started_at = datetime.now(timezone.utc)

        if kwargs.get("status") == StepStatus.COMPLETED and not step.completed_at:
            step.completed_at = datetime.now(timezone.utc)

        return await self._flow_repo.update_step(step)


class FlowAddStep:

    def __init__(self, flow_repo: FlowRepository) -> None:
        self._flow_repo = flow_repo

    async def execute(self, flow_id: str, agent_type: str, name: str, order: int, depends_on_step_id: str | None = None) -> FlowStep:
        flow = await self._flow_repo.get_by_id(flow_id)
        if not flow:
            raise FlowNotFoundError(f"Flow {flow_id} no encontrado")

        step = FlowStep(
            flow_id=flow_id,
            agent_type=agent_type,
            name=name,
            order=order,
            status=StepStatus.PENDING,
            depends_on_step_id=depends_on_step_id,
        )
        return await self._flow_repo.add_step(step)