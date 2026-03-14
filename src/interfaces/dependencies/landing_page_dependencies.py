from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from infra.config.database import get_session
from infra.adapters.landing_page_sqlalchemy import LandingPageSQLAlchemyRepository
from domain.repositories.landing_page_repository import LandingPageRepository
from app.use_cases.landing_page_crud import (
    LandingPageCreate, LandingPageList, LandingPageUpdate, LandingPageDelete, LandingSectionUpdate,
)


def get_lp_repository(session: AsyncSession = Depends(get_session)) -> LandingPageRepository:
    return LandingPageSQLAlchemyRepository(session)

def get_lp_create(repo: LandingPageRepository = Depends(get_lp_repository)) -> LandingPageCreate:
    return LandingPageCreate(repo)

def get_lp_list(repo: LandingPageRepository = Depends(get_lp_repository)) -> LandingPageList:
    return LandingPageList(repo)

def get_lp_update(repo: LandingPageRepository = Depends(get_lp_repository)) -> LandingPageUpdate:
    return LandingPageUpdate(repo)

def get_lp_delete(repo: LandingPageRepository = Depends(get_lp_repository)) -> LandingPageDelete:
    return LandingPageDelete(repo)

def get_section_update(repo: LandingPageRepository = Depends(get_lp_repository)) -> LandingSectionUpdate:
    return LandingSectionUpdate(repo)