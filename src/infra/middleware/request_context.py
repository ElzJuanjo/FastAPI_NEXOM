"""
Middleware que asigna un request_id único a cada request
y lo propaga a los logs via structlog contextvars.
"""

import uuid
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Inyectar en structlog contextvars (disponible en todos los logs de este request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Inyectar en request.state para que otros middlewares/dependencies lo usen
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response