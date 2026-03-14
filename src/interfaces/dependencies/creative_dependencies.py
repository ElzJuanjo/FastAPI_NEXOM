from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from infra.config.database import get_session
from infra.adapters.creative_sqlalchemy import CreativeSQLAlchemyRepository
from domain.repositories.creative_repository import CreativeRepository
from app.use_cases.creative_crud import CreativeCreate, CreativeList, CreativeUpdate, CreativeDelete


def get_creative_repository(session: AsyncSession = Depends(get_session)) -> CreativeRepository:
    return CreativeSQLAlchemyRepository(session)

def get_creative_create(repo: CreativeRepository = Depends(get_creative_repository)) -> CreativeCreate:
    return CreativeCreate(repo)

def get_creative_list(repo: CreativeRepository = Depends(get_creative_repository)) -> CreativeList:
    return CreativeList(repo)

def get_creative_update(repo: CreativeRepository = Depends(get_creative_repository)) -> CreativeUpdate:
    return CreativeUpdate(repo)

def get_creative_delete(repo: CreativeRepository = Depends(get_creative_repository)) -> CreativeDelete:
    return CreativeDelete(repo)