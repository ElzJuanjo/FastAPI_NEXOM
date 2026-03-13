"""
Dependencias de inyección para Flow.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from infra.adapters.flow_sqlalchemy import FlowSQLAlchemyRepository
from domain.repositories.flow_repository import FlowRepository
from app.use_cases.flow_crud import (
    FlowCreate, FlowList, FlowUpdate, FlowDelete,
    FlowStepUpdate, FlowAddStep,
)


def get_flow_repository(session: AsyncSession = Depends(get_session)) -> FlowRepository:
    return FlowSQLAlchemyRepository(session)


def get_flow_create(repo: FlowRepository = Depends(get_flow_repository)) -> FlowCreate:
    return FlowCreate(repo)


def get_flow_list(repo: FlowRepository = Depends(get_flow_repository)) -> FlowList:
    return FlowList(repo)


def get_flow_update(repo: FlowRepository = Depends(get_flow_repository)) -> FlowUpdate:
    return FlowUpdate(repo)


def get_flow_delete(repo: FlowRepository = Depends(get_flow_repository)) -> FlowDelete:
    return FlowDelete(repo)


def get_flow_step_update(repo: FlowRepository = Depends(get_flow_repository)) -> FlowStepUpdate:
    return FlowStepUpdate(repo)


def get_flow_add_step(repo: FlowRepository = Depends(get_flow_repository)) -> FlowAddStep:
    return FlowAddStep(repo)