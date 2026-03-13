"""
Caso de uso: Registro de usuario por email.
Idempotente — si el email ya existe, lanza error controlado.
"""

from domain.entities.user import User, UserAuthProvider
from domain.entities.base import AuthProvider
from domain.repositories.user_repository import UserRepository
from infra.config.security import hash_password, create_access_token, create_refresh_token


class EmailAlreadyExistsError(Exception):
    pass


class AuthRegister:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, email: str, full_name: str, password: str) -> dict:
        # Idempotencia: verificar que no exista
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise EmailAlreadyExistsError(f"El email {email} ya está registrado")

        # Crear usuario
        user = User(
            email=email,
            full_name=full_name,
            is_active=True,
            is_verified=False,
        )

        user = await self._user_repo.create(user)

        # Crear auth provider con password hasheado
        auth_provider = UserAuthProvider(
            user_id=user.id,
            provider=AuthProvider.EMAIL,
            provider_email=email,
            password_hash=hash_password(password),
        )
        await self._user_repo.create_auth_provider(auth_provider)

        # Generar tokens
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }