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
    AuthResponse, AuthLoginResponse, UserResponse, TokenResponse,
    VerifyEmailRequest, VerifyEmailResponse,
    ResendVerificationRequest, ResendVerificationResponse,
    ChangePasswordRequest, ChangePasswordResponse,
    Setup2FAResponse, Verify2FARequest, Verify2FAResponse, Disable2FARequest,
    Verify2FALoginRequest,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)
from app.use_cases.auth.register import AuthRegister, EmailAlreadyExistsError
from app.use_cases.auth.login import AuthLogin, InvalidCredentialsError, InactiveUserError
from app.use_cases.auth.refresh import AuthRefresh, InvalidRefreshTokenError
from interfaces.dependencies.auth_dependencies import (
    get_auth_register, get_auth_login, get_auth_refresh,
    get_current_user_id, get_user_repository,
)
from domain.repositories.user_repository import UserRepository
from infra.tools.google_oauth_client import get_google_login_url, GoogleOAuthError
from app.use_cases.auth.google import GoogleAuth, GoogleAuthError
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

@router.post("/login", response_model=AuthLoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    use_case: AuthLogin = Depends(get_auth_login),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await use_case.execute(email=body.email, password=body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o contraseña incorrectos.")
    except InactiveUserError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu cuenta está desactivada. Contacta soporte.")

    user = result["user"]

    # Si tiene 2FA habilitado, no entregar tokens todavía
    if user.is_2fa_enabled and user.totp_secret:
        from infra.config.security import create_access_token
        # Crear token temporal de corta vida (5 min) solo para completar 2FA
        temp_token = create_access_token(
            subject=user.id,
            extra_claims={"purpose": "2fa_verification"},
            expires_minutes=5,
        )

        return AuthLoginResponse(
            requires_2fa=True,
            temp_token=temp_token,
        )

    _set_refresh_cookie(response, result["refresh_token"])

    return AuthLoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(access_token=result["access_token"]),
        requires_2fa=False,
    )


# ---------------------------------------------------------------------------
# Login — 2FA Verification Step
# ---------------------------------------------------------------------------

@router.post("/login/2fa", response_model=AuthLoginResponse)
@limiter.limit("10/minute")
async def login_verify_2fa(
    request: Request,
    body: Verify2FALoginRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """Segundo paso del login: verificar código TOTP."""
    import pyotp
    from infra.config.security import decode_access_token, create_access_token, create_refresh_token

    # Decodificar temp token
    try:
        payload = decode_access_token(body.temp_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token temporal inválido o expirado. Inicia sesión de nuevo.")

    if payload.get("purpose") != "2fa_verification":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no válido para verificación 2FA.")

    user_id = payload.get("sub")
    user = await user_repo.get_by_id(user_id)
    if not user or not user.totp_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado.")

    # Verificar código TOTP
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código 2FA inválido. Verifica e intenta de nuevo.")

    # Generar tokens reales
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    _set_refresh_cookie(response, refresh_token)

    return AuthLoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(access_token=access_token),
        requires_2fa=False,
    )


# ---------------------------------------------------------------------------
# Forgot Password
# ---------------------------------------------------------------------------

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Envía email con link para resetear contraseña. Siempre retorna 200 por seguridad."""
    user = await user_repo.get_by_email(body.email)

    if user and user.is_active:
        try:
            token = create_verification_token(subject=user.id, expires_minutes=15)
            # Reutilizar el email client para enviar reset
            from infra.tools.email_client import send_email
            reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            await send_email(
                to=user.email,
                subject="Restablecer contraseña — NexOS",
                html_body=f"""
                <h2>Hola {user.full_name},</h2>
                <p>Recibimos una solicitud para restablecer tu contraseña.</p>
                <p><a href="{reset_link}" style="display:inline-block;padding:12px 24px;background:#7c3aed;color:white;text-decoration:none;border-radius:8px;font-weight:bold;">Restablecer contraseña</a></p>
                <p>Este enlace expira en 15 minutos.</p>
                <p>Si no solicitaste este cambio, ignora este correo.</p>
                <br><p>— Equipo NexOS</p>
                """,
            )
        except Exception as e:
            logger.error(f"Error enviando reset password a {body.email}: {e}")

    return ForgotPasswordResponse(
        message="Si el email está registrado, recibirás instrucciones para restablecer tu contraseña.",
    )


# ---------------------------------------------------------------------------
# Reset Password (con token del email)
# ---------------------------------------------------------------------------

@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Restablece la contraseña usando el token recibido por email."""
    from infra.config.security import hash_password
    from domain.entities.user import UserAuthProvider
    from domain.entities.base import AuthProvider
    from sqlalchemy import select

    try:
        payload = decode_verification_token(body.token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace ha expirado. Solicita uno nuevo.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enlace inválido.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido.")

    # Buscar auth provider de email
    stmt = select(UserAuthProvider).where(
        UserAuthProvider.user_id == user_id,
        UserAuthProvider.provider == AuthProvider.EMAIL,
    )
    result = await session.execute(stmt)
    email_provider = result.scalar_one_or_none()

    if not email_provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se encontró cuenta con autenticación por email.")

    email_provider.password_hash = hash_password(body.new_password)
    await session.commit()

    return ResetPasswordResponse(message="Contraseña restablecida exitosamente. Ya puedes iniciar sesión.")


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
@limiter.limit("1/30minutes")
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
# Change Password
# ---------------------------------------------------------------------------

@router.post("/change-password", response_model=ChangePasswordResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """Cambiar contraseña del usuario autenticado."""
    from infra.config.security import verify_password, hash_password
    from domain.entities.user import UserAuthProvider
    from domain.entities.base import AuthProvider
    from sqlalchemy import select

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Buscar el provider de email
    stmt = select(UserAuthProvider).where(
        UserAuthProvider.user_id == user_id,
        UserAuthProvider.provider == AuthProvider.EMAIL,
    )
    result = await session.execute(stmt)
    email_provider = result.scalar_one_or_none()

    if not email_provider or not email_provider.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta usa Google para autenticarse. No puedes cambiar la contraseña.",
        )

    # Verificar contraseña actual
    if not verify_password(body.current_password, email_provider.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )

    # Verificar que la nueva sea diferente
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente a la actual.",
        )

    email_provider.password_hash = hash_password(body.new_password)
    await session.commit()

    return ChangePasswordResponse(message="Contraseña actualizada exitosamente.")


# ---------------------------------------------------------------------------
# 2FA — Setup
# ---------------------------------------------------------------------------

@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """Genera un secreto TOTP y retorna el QR para Google Authenticator."""
    import pyotp
    import qrcode
    import io
    import base64

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA ya está habilitado. Desactívalo primero si quieres regenerar.",
        )

    # Generar secreto TOTP
    secret = pyotp.random_base32()
    user.totp_secret = secret
    await session.commit()

    # Generar URL para apps de autenticación
    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(name=user.email, issuer_name="NexOS")

    # Generar QR como base64
    qr = qrcode.make(otpauth_url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return Setup2FAResponse(
        secret=secret,
        otpauth_url=otpauth_url,
        qr_base64=f"data:image/png;base64,{qr_base64}",
    )


# ---------------------------------------------------------------------------
# 2FA — Verify & Enable
# ---------------------------------------------------------------------------

@router.post("/2fa/verify", response_model=Verify2FAResponse)
async def verify_2fa(
    body: Verify2FARequest,
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """Verifica el código TOTP y activa 2FA."""
    import pyotp

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero debes configurar 2FA con /2fa/setup.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido. Verifica e intenta de nuevo.",
        )

    user.is_2fa_enabled = True
    await session.commit()

    return Verify2FAResponse(
        message="2FA activado exitosamente.",
        is_2fa_enabled=True,
    )
    
    
@router.get("/me/verification-status")
async def get_verification_status(
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Returns verification status and token expiry info."""
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "is_verified": user.is_verified,
        "email": user.email,
        "verification_expires_hours": settings.JWT_VERIFICATION_TOKEN_EXPIRE_HOURS,
    }


# ---------------------------------------------------------------------------
# 2FA — Disable
# ---------------------------------------------------------------------------

@router.post("/2fa/disable", response_model=Verify2FAResponse)
async def disable_2fa(
    body: Disable2FARequest,
    user_id: str = Depends(get_current_user_id),
    user_repo: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_session),
):
    """Desactiva 2FA verificando con un código válido."""
    import pyotp

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA no está habilitado.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido.",
        )

    user.is_2fa_enabled = False
    user.totp_secret = None
    await session.commit()

    return Verify2FAResponse(
        message="2FA desactivado.",
        is_2fa_enabled=False,
    )


# ---------------------------------------------------------------------------
# Referral Info
# ---------------------------------------------------------------------------

@router.get("/me/referral")
async def get_referral_info(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Retorna el link de referido, estadísticas y lista de referidos."""
    from domain.entities.user import User
    from sqlalchemy import select, func

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get referred users with their emails
    referrals_stmt = (
        select(User.email, User.full_name, User.created_at)
        .where(User.referred_by_user_id == user_id, User.deleted_at.is_(None))
        .order_by(User.created_at.desc())
    )
    referrals_result = await session.execute(referrals_stmt)
    referrals = [
        {"email": r.email, "name": r.full_name, "joined_at": str(r.created_at)}
        for r in referrals_result.all()
    ]

    total_referrals = len(referrals)
    credits_earned = total_referrals * 15  # 15 credits per referral

    return {
        "referral_code": user.referral_code,
        "referral_link": f"{settings.FRONTEND_URL}?ref={user.referral_code}",
        "total_referrals": total_referrals,
        "credits_earned": credits_earned,
        "referrals": referrals,
    }
