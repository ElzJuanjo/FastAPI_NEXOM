"""
Casos de uso para AgentTask — listar historial de ejecuciones.
"""

from typing import List

from domain.entities.agent import AgentTask
from domain.repositories.agent_task_repository import AgentTaskRepository


class AgentTaskNotFoundError(Exception):
    pass


class AgentTaskList:

    def __init__(self, task_repo: AgentTaskRepository) -> None:
        self._task_repo = task_repo

    async def execute(self, org_id: str, agent_type: str | None = None, limit: int = 20) -> List[AgentTask]:
        """
        Lista tasks de la organización.
        Si se proporciona agent_type, filtra por ese tipo.
        """
        if agent_type:
            return await self._task_repo.list_by_org_and_type(org_id, agent_type, limit)
        return await self._task_repo.list_by_organization(org_id, limit)
