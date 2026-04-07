"""
Caso de uso: Renovar access token usando refresh token.
"""

import jwt

from domain.repositories.user_repository import UserRepository
from infra.config.security import decode_token, create_access_token, create_refresh_token


class InvalidRefreshTokenError(Exception):
    pass


class AuthRefresh:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise InvalidRefreshTokenError("Refresh token expirado")
        except jwt.InvalidTokenError:
            raise InvalidRefreshTokenError("Refresh token inválido")

        if payload.get("type") != "refresh":
            raise InvalidRefreshTokenError("El token no es de tipo refresh")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidRefreshTokenError("Token sin subject")

        user = await self._user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidRefreshTokenError("Usuario no encontrado o inactivo")

        # Rotar tokens (seguridad: el refresh anterior queda obsoleto por expiración)
        new_access = create_access_token(subject=user.id)
        new_refresh = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": new_access,
            "refresh_token": new_refresh,
        }