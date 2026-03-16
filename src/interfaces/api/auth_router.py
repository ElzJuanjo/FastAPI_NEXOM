"""
Endpoints de autenticación: register, login, refresh, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from app.dto.auth_dto import (
    RegisterRequest, LoginRequest, RefreshRequest,
    AuthResponse, UserResponse, TokenResponse,
)
from app.use_cases.auth_register import AuthRegister, EmailAlreadyExistsError
from app.use_cases.auth_login import AuthLogin, InvalidCredentialsError, InactiveUserError
from app.use_cases.auth_refresh import AuthRefresh, InvalidRefreshTokenError
from interfaces.dependencies.auth_dependencies import (
    get_auth_register, get_auth_login, get_auth_refresh,
    get_current_user_id, get_user_repository,
)
from domain.repositories.user_repository import UserRepository
from infra.tools.google_oauth_client import get_google_login_url, GoogleOAuthError
from app.use_cases.auth_google import GoogleAuth, GoogleAuthError

from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    use_case: AuthRegister = Depends(get_auth_register),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await use_case.execute(
            email=body.email,
            full_name=body.full_name,
            password=body.password,
        )
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await session.commit()

    return AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        tokens=TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        ),
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    use_case: AuthLogin = Depends(get_auth_login),
):
    try:
        result = await use_case.execute(email=body.email, password=body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except InactiveUserError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        tokens=TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    use_case: AuthRefresh = Depends(get_auth_refresh),
):
    try:
        result = await use_case.execute(refresh_token=body.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
):
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return UserResponse.model_validate(user)


@router.get("/google/login")
async def google_login():
    """Retorna la URL para iniciar el flujo de login con Google."""
    from infra.config.database import settings
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no configurado",
        )
    url = get_google_login_url()
    return {"login_url": url}


@router.get("/google/callback")
async def google_callback(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Callback de Google OAuth.
    Recibe el authorization code, lo intercambia por tokens,
    crea/loguea al usuario y retorna JWT de NexOS.
    """
    from infra.adapters.user_sqlalchemy import UserSQLAlchemyRepository

    user_repo = UserSQLAlchemyRepository(session)
    use_case = GoogleAuth(user_repo)

    try:
        result = await use_case.execute(code=code)
    except GoogleAuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await session.commit()
    return result