"""
Dependencias de inyección para auth.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from infra.config.database import get_session
from infra.config.security import decode_token
from infra.adapters.user_sqlalchemy import UserSQLAlchemyRepository
from domain.repositories.user_repository import UserRepository
from app.use_cases.auth_register import AuthRegister
from app.use_cases.auth_login import AuthLogin
from app.use_cases.auth_refresh import AuthRefresh


# ---------------------------------------------------------------------------
# Repositorio
# ---------------------------------------------------------------------------

def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserSQLAlchemyRepository(session)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------

def get_auth_register(repo: UserRepository = Depends(get_user_repository)) -> AuthRegister:
    return AuthRegister(repo)


def get_auth_login(repo: UserRepository = Depends(get_user_repository)) -> AuthLogin:
    return AuthLogin(repo)


def get_auth_refresh(repo: UserRepository = Depends(get_user_repository)) -> AuthRefresh:
    return AuthRefresh(repo)


# ---------------------------------------------------------------------------
# Middleware: obtener usuario actual desde Bearer token
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Extrae y valida el access token. Retorna el user_id."""
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no es de tipo access")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin subject")

    return user_id