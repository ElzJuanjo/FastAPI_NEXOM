"""
Casos de uso para AgentConfig.
Idempotente: no permite duplicar (org_id, agent_type).
"""

from typing import List

from domain.entities.agent import AgentConfig
from domain.repositories.agent_config_repository import AgentConfigRepository


class AgentConfigAlreadyExistsError(Exception):
    pass


class AgentConfigNotFoundError(Exception):
    pass


class AgentConfigCreate:

    def __init__(self, repo: AgentConfigRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: str, agent_type: str, ai_provider: str, model_version: str, is_enabled: bool = True, config_params: dict | None = None) -> AgentConfig:
        # Idempotencia: verificar que no exista la combinación
        existing = await self._repo.get_by_org_and_type(org_id, agent_type)
        if existing:
            raise AgentConfigAlreadyExistsError(
                f"El agente '{agent_type}' ya está configurado para esta organización"
            )

        config = AgentConfig(
            organization_id=org_id,
            agent_type=agent_type,
            ai_provider=ai_provider,
            model_version=model_version,
            is_enabled=is_enabled,
            config_params=config_params,
        )
        return await self._repo.create(config)


class AgentConfigList:

    def __init__(self, repo: AgentConfigRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: str) -> List[AgentConfig]:
        return await self._repo.list_by_organization(org_id)


class AgentConfigUpdate:

    def __init__(self, repo: AgentConfigRepository) -> None:
        self._repo = repo

    async def execute(self, config_id: str, **kwargs) -> AgentConfig:
        config = await self._repo.get_by_id(config_id)
        if not config:
            raise AgentConfigNotFoundError(f"AgentConfig {config_id} no encontrado")

        for key, value in kwargs.items():
            if value is not None:
                setattr(config, key, value)

        return await self._repo.update(config)