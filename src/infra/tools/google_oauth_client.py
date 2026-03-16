"""
Cliente para Google OAuth 2.0.
Flujo Authorization Code: intercambia code por tokens y obtiene perfil del usuario.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from infra.config.database import settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuthError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def get_google_login_url(state: str = "") -> str:
    """Genera la URL a la que el frontend redirige al usuario para autenticarse con Google."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """
    Intercambia el authorization code por access_token y refresh_token.

    Returns:
        Dict con: access_token, refresh_token, expires_in, id_token, token_type
    """
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)

    if response.status_code != 200:
        raise GoogleOAuthError(f"Error intercambiando code: {response.text}")

    data = response.json()
    if "access_token" not in data:
        raise GoogleOAuthError(f"No se recibió access_token: {data}")

    return data


async def get_google_user_info(access_token: str) -> dict:
    """
    Obtiene el perfil del usuario de Google.

    Returns:
        Dict con: id, email, name, picture, verified_email
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise GoogleOAuthError(f"Error obteniendo perfil: {response.text}")

    return response.json()