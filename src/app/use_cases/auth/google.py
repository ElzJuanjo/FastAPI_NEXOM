"""
Caso de uso: Autenticación con Google OAuth.
Crea el usuario si no existe, o lo loguea si ya existe.
Soporta vincular Google a una cuenta email existente.

Flujo con frontend:
- Genera access_token + refresh_token de NexOS
- Retorna ambos tokens (el router se encarga de setear la cookie
  y redirigir con el access_token en la URL).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from domain.entities.user import User, UserAuthProvider
from domain.entities.base import AuthProvider
from domain.repositories.user_repository import UserRepository
from infra.config.security import create_access_token, create_refresh_token
from infra.tools.google_oauth_client import (
    exchange_code_for_tokens,
    get_google_user_info,
    GoogleOAuthError,
)
import secrets
import string


def _generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


class GoogleAuthError(Exception):
    pass


class GoogleAuth:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, code: str) -> dict:
        """
        Flujo completo de Google OAuth:
        1. Intercambiar code por tokens de Google
        2. Obtener perfil de Google
        3. Buscar usuario existente por email o provider_user_id
        4. Crear usuario si no existe
        5. Vincular provider si usuario existe pero no tiene Google
        6. Generar JWT de NexOS

        Returns:
            Dict con: access_token, refresh_token, user, is_new_user
        """
        # 1. Intercambiar code
        try:
            tokens = await exchange_code_for_tokens(code)
        except GoogleOAuthError as e:
            raise GoogleAuthError(f"Error con Google: {e.detail}")

        access_token_google = tokens["access_token"]
        refresh_token_google = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)

        # 2. Obtener perfil
        try:
            profile = await get_google_user_info(access_token_google)
        except GoogleOAuthError as e:
            raise GoogleAuthError(f"Error obteniendo perfil: {e.detail}")

        google_id = profile.get("id")
        email = profile.get("email")
        name = profile.get("name", "")
        picture = profile.get("picture", "")
        verified = profile.get("verified_email", False)

        if not email:
            raise GoogleAuthError("Google no proporcionó email")

        if not verified:
            raise GoogleAuthError("Email de Google no verificado")

        # 3. Buscar usuario existente
        existing_user = await self._user_repo.get_by_email(email)
        is_new_user = False

        if existing_user:
            user = existing_user

            # Verificar si ya tiene provider Google
            has_google = any(
                p.provider == AuthProvider.GOOGLE
                for p in user.auth_providers
            )

            if not has_google:
                # 5. Vincular Google a cuenta existente
                google_provider = UserAuthProvider(
                    user_id=user.id,
                    provider=AuthProvider.GOOGLE,
                    provider_user_id=google_id,
                    provider_email=email,
                    access_token=access_token_google,
                    refresh_token=refresh_token_google,
                    token_expires_at=datetime.fromtimestamp(
                        datetime.now(timezone.utc).timestamp() + expires_in,
                        tz=timezone.utc,
                    ),
                )
                await self._user_repo.add_auth_provider(google_provider)
            else:
                # Actualizar tokens del provider Google existente
                for p in user.auth_providers:
                    if p.provider == AuthProvider.GOOGLE:
                        p.access_token = access_token_google
                        if refresh_token_google:
                            p.refresh_token = refresh_token_google
                        p.token_expires_at = datetime.fromtimestamp(
                            datetime.now(timezone.utc).timestamp() + expires_in,
                            tz=timezone.utc,
                        )
                        break

            # Actualizar avatar si no tiene
            if not user.avatar_url and picture:
                user.avatar_url = picture

            # Google verifica el email por nosotros
            user.is_verified = True

        else:
            # 4. Crear usuario nuevo
            is_new_user = True

            user = User(
                email=email,
                full_name=name,
                avatar_url=picture,
                is_active=True,
                is_verified=True,  # Google ya verificó el email
                referral_code=_generate_referral_code(),
            )
            user = await self._user_repo.create(user)

            google_provider = UserAuthProvider(
                user_id=user.id,
                provider=AuthProvider.GOOGLE,
                provider_user_id=google_id,
                provider_email=email,
                access_token=access_token_google,
                refresh_token=refresh_token_google,
                token_expires_at=datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + expires_in,
                    tz=timezone.utc,
                ),
            )
            await self._user_repo.add_auth_provider(google_provider)

        # 6. Generar JWT de NexOS
        nexos_access_token = create_access_token(subject=user.id)
        nexos_refresh_token = create_refresh_token(subject=user.id)

        return {
            "user": user,
            "access_token": nexos_access_token,
            "refresh_token": nexos_refresh_token,
            "is_new_user": is_new_user,
        }
