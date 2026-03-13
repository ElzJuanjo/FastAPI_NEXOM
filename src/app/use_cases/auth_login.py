"""
Caso de uso: Login por email + password.
"""

from domain.entities.base import AuthProvider
from domain.repositories.user_repository import UserRepository
from infra.config.security import verify_password, create_access_token, create_refresh_token


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthLogin:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, email: str, password: str) -> dict:
        user = await self._user_repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsError("Credenciales inválidas")

        if not user.is_active:
            raise InactiveUserError("La cuenta está desactivada")

        # Buscar provider de tipo EMAIL
        email_provider = next(
            (p for p in user.auth_providers if p.provider == AuthProvider.EMAIL),
            None,
        )
        if not email_provider or not email_provider.password_hash:
            raise InvalidCredentialsError("Credenciales inválidas")

        if not verify_password(password, email_provider.password_hash):
            raise InvalidCredentialsError("Credenciales inválidas")

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }