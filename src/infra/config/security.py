"""
Hashing y generación/verificación de JWT.
Incluye tokens de acceso, refresh y verificación de email.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .database import settings


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_verification_token(subject: str) -> str:
    """Genera un JWT de corta duración para verificar email."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_VERIFICATION_TOKEN_EXPIRE_HOURS),
        "type": "email_verification",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_verification_token(token: str) -> dict:
    """
    Decodifica un token de verificación de email.
    Lanza jwt.ExpiredSignatureError o jwt.InvalidTokenError si falla.
    Valida que el tipo sea 'email_verification'.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "email_verification":
        raise jwt.InvalidTokenError("Token no es de tipo email_verification")
    return payload


def decode_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza jwt.ExpiredSignatureError o jwt.InvalidTokenError."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
