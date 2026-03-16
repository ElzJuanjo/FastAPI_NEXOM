"""
Manejo global de errores para FastAPI.
Captura excepciones no manejadas y retorna respuestas JSON consistentes.
"""

import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Excepciones de dominio base
# ---------------------------------------------------------------------------

class NexOSError(Exception):
    """Excepción base de NexOS."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "Error interno del servidor"

    def __init__(self, message: str | None = None, detail: str | None = None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(NexOSError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Recurso no encontrado"


class ForbiddenError(NexOSError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "No tienes permisos para esta acción"


class QuotaExceededError(NexOSError):
    status_code = 429
    error_code = "QUOTA_EXCEEDED"
    message = "Cuota mensual excedida"


class ExternalServiceError(NexOSError):
    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "Error en servicio externo"


class ValidationError(NexOSError):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Error de validación"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def nexos_error_handler(request: Request, exc: NexOSError) -> JSONResponse:
    """Handler para excepciones de dominio de NexOS."""
    logger.warning(
        "nexos_error",
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler para excepciones HTTP de FastAPI/Starlette."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "detail": None,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler para excepciones no manejadas — nunca expone traceback al usuario."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "Error interno del servidor. Si el problema persiste, contacta soporte.",
            "detail": None,
        },
    )