"""
Implementación SQLAlchemy async del UserRepository.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities.user import User, UserAuthProvider
from domain.repositories.user_repository import UserRepository


class UserSQLAlchemyRepository(UserRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.auth_providers))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.auth_providers))
            .where(User.email == email, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_auth_provider(self, user_id: str, provider: str) -> Optional[UserAuthProvider]:
        stmt = select(UserAuthProvider).where(
            UserAuthProvider.user_id == user_id,
            UserAuthProvider.provider == provider,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_auth_provider(self, auth_provider: UserAuthProvider) -> UserAuthProvider:
        self._session.add(auth_provider)
        await self._session.flush()
        return auth_provider
    
    async def add_auth_provider(self, provider) -> object:
        self._session.add(provider)
        await self._session.flush()
        return provider
    
    async def get_by_referral_code(self, code: str):
        from domain.entities.user import User
        stmt = select(User).where(User.referral_code == code, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()