"""
Endpoints de autenticación: register, login, refresh, logout, me,
verify-email, resend-verification, Google OAuth.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session, settings
from app.dto.auth_dto import (
    RegisterRequest, LoginRequest,
    AuthResponse, UserResponse, TokenResponse,
    VerifyEmailRequest, VerifyEmailResponse,
    ResendVerificationRequest, ResendVerificationResponse,
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
from infra.config.security import create_verification_token, decode_verification_token
from infra.tools.email_client import send_verification_email

from infra.middleware.rate_limiter import limiter
from starlette.requests import Request

import jwt as pyjwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Helpers — Cookie de refresh token
# ---------------------------------------------------------------------------

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Setea el refresh token como cookie httpOnly segura."""
    is_production = settings.APP_ENV == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        path="/api/v1/auth",  # Solo accesible desde endpoints de auth
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


def _delete_refresh_cookie(response: Response) -> None:
    """Elimina la cookie de refresh token."""
    response.delete_cookie("refresh_token", path="/api/v1/auth")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    use_case: AuthRegister = Depends(get_auth_register),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await use_case.execute(
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            referral_code=body.referral_code,
        )
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await session.commit()

    _set_refresh_cookie(response, result["refresh_token"])

    return AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        tokens=TokenResponse(
            access_token=result["access_token"],
        ),
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    use_case: AuthLogin = Depends(get_auth_login),
):
    try:
        result = await use_case.execute(email=body.email, password=body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except InactiveUserError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    _set_refresh_cookie(response, result["refresh_token"])

    return AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        tokens=TokenResponse(
            access_token=result["access_token"],
        ),
    )


# ---------------------------------------------------------------------------
# Refresh (lee refresh token de cookie)
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    use_case: AuthRefresh = Depends(get_auth_refresh),
):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        result = await use_case.execute(refresh_token=refresh_token)
    except InvalidRefreshTokenError as e:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Rotar cookie con nuevo refresh token
    _set_refresh_cookie(response, result["refresh_token"])

    return TokenResponse(
        access_token=result["access_token"],
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(response: Response):
    _delete_refresh_cookie(response)
    return {"message": "ok"}


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
):
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Verify Email
# ---------------------------------------------------------------------------

@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    body: VerifyEmailRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """
    Verifica el email del usuario usando el token recibido por correo.
    El frontend llama a este endpoint cuando el usuario hace clic en el link.
    """
    try:
        payload = decode_verification_token(body.token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación ha expirado. Solicita uno nuevo.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido.",
        )

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if user.is_verified:
        return VerifyEmailResponse(
            message="El email ya estaba verificado.",
            is_verified=True,
        )

    user.is_verified = True
    await session.commit()

    return VerifyEmailResponse(
        message="Email verificado exitosamente.",
        is_verified=True,
    )


# ---------------------------------------------------------------------------
# Resend Verification Email
# ---------------------------------------------------------------------------

@router.post("/resend-verification", response_model=ResendVerificationResponse)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Reenvía el email de verificación.
    Siempre retorna 200 para no filtrar si el email existe o no.
    """
    user = await user_repo.get_by_email(body.email)

    if user and not user.is_verified:
        try:
            verification_token = create_verification_token(subject=user.id)
            await send_verification_email(
                to=user.email,
                full_name=user.full_name,
                verification_token=verification_token,
            )
        except Exception as e:
            logger.error(f"Error reenviando verificación a {body.email}: {e}")

    # Siempre respondemos igual (seguridad: no filtrar existencia de cuentas)
    return ResendVerificationResponse(
        message="Si el email está registrado y no verificado, recibirás un correo de verificación.",
    )


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@router.get("/google/login")
async def google_login():
    """Redirige al usuario a Google para autenticarse."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no configurado",
        )
    url = get_google_login_url()
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Callback de Google OAuth.
    Recibe el authorization code, lo intercambia por tokens,
    crea/loguea al usuario, setea refresh_token en cookie
    y redirige al frontend con access_token en URL.
    """
    from infra.adapters.user_sqlalchemy import UserSQLAlchemyRepository

    user_repo = UserSQLAlchemyRepository(session)
    use_case = GoogleAuth(user_repo)

    try:
        result = await use_case.execute(code=code)
    except GoogleAuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await session.commit()

    # Construir redirect al frontend
    # access_token va en la URL (el frontend lo captura y guarda en localStorage)
    # refresh_token va en cookie httpOnly (invisible para JS)
    is_production = settings.APP_ENV == "production"

    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?access_token={result['access_token']}&is_new_user={str(result['is_new_user']).lower()}",
        status_code=status.HTTP_302_FOUND,
    )

    redirect.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=is_production,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return redirect


# ---------------------------------------------------------------------------
# Referral Info
# ---------------------------------------------------------------------------

@router.get("/me/referral")
async def get_referral_info(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Retorna el link de referido del usuario y estadísticas."""
    from domain.entities.user import User
    from sqlalchemy import select, func

    # Obtener usuario
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Contar referidos
    count_stmt = select(func.count()).select_from(User).where(
        User.referred_by_user_id == user_id,
        User.deleted_at.is_(None),
    )
    count_result = await session.execute(count_stmt)
    total_referrals = count_result.scalar() or 0

    return {
        "referral_code": user.referral_code,
        "referral_link": f"{settings.FRONTEND_URL}?ref={user.referral_code}",
        "total_referrals": total_referrals,
    }
