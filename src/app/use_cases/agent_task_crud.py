"""
Casos de uso para AgentTask.
"""

from datetime import datetime, timezone
from typing import List

from domain.entities.agent import AgentTask
from domain.entities.base import StepStatus
from domain.repositories.agent_task_repository import AgentTaskRepository
from domain.repositories.agent_config_repository import AgentConfigRepository


class AgentConfigNotFoundForTaskError(Exception):
    pass


class AgentTaskNotFoundError(Exception):
    pass


class AgentTaskCreate:

    def __init__(self, task_repo: AgentTaskRepository, config_repo: AgentConfigRepository) -> None:
        self._task_repo = task_repo
        self._config_repo = config_repo

    async def execute(self, agent_config_id: str, input_payload: dict | None = None) -> AgentTask:
        # Verificar que el config existe
        config = await self._config_repo.get_by_id(agent_config_id)
        if not config:
            raise AgentConfigNotFoundForTaskError(f"AgentConfig {agent_config_id} no encontrado")

        # Incrementar contador de tasks totales
        config.tasks_total += 1

        task = AgentTask(
            agent_config_id=agent_config_id,
            status=StepStatus.PENDING,
            input_payload=input_payload,
        )
        return await self._task_repo.create(task)


class AgentTaskList:

    def __init__(self, task_repo: AgentTaskRepository) -> None:
        self._task_repo = task_repo

    async def execute(self, config_id: str, limit: int = 20) -> List[AgentTask]:
        return await self._task_repo.list_by_config(config_id, limit)