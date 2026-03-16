"""
Rate limiting con SlowAPI + Redis backend.
Limita requests por IP y por usuario autenticado.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from infra.config.database import settings


def _get_key(request: Request) -> str:
    """
    Genera la key de rate limit.
    Si hay usuario autenticado (JWT), usa user_id.
    Si no, usa la IP.
    """
    # Intentar extraer user_id del state (inyectado por auth dependency)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_key,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handler custom para cuando se excede el rate limit."""
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Demasiadas solicitudes. Intenta de nuevo en unos momentos.",
            "detail": str(exc.detail),
        },
    )