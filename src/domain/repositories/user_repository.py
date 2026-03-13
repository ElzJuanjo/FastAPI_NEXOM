"""
Contrato de acceso a datos para User y UserAuthProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional

from domain.entities.user import User, UserAuthProvider


class UserRepository(ABC):

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        ...

    @abstractmethod
    async def get_auth_provider(self, user_id: str, provider: str) -> Optional[UserAuthProvider]:
        ...

    @abstractmethod
    async def create_auth_provider(self, auth_provider: UserAuthProvider) -> UserAuthProvider:
        ...