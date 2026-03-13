"""
Implementación SQLAlchemy async del OrganizationRepository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.organization import Organization, OrganizationMember
from domain.repositories.organization_repository import OrganizationRepository


class OrganizationSQLAlchemyRepository(OrganizationRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, org_id: str) -> Optional[Organization]:
        stmt = (
            select(Organization)
            .options(selectinload(Organization.plan), selectinload(Organization.members))
            .where(Organization.id == org_id, Organization.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        stmt = (
            select(Organization)
            .options(selectinload(Organization.plan))
            .where(Organization.slug == slug, Organization.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, organization: Organization) -> Organization:
        self._session.add(organization)
        await self._session.flush()
        return organization

    async def get_member(self, org_id: str, user_id: str) -> Optional[OrganizationMember]:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(self, member: OrganizationMember) -> OrganizationMember:
        self._session.add(member)
        await self._session.flush()
        return member

    async def list_by_user(self, user_id: str) -> List[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .options(selectinload(Organization.plan))
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.deleted_at.is_(None),
                Organization.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())