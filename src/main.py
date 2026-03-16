from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infra.config.logging import setup_logging
from infra.middleware.request_context import RequestContextMiddleware
from infra.middleware.error_handler import (
    NexOSError, nexos_error_handler,
    http_exception_handler, unhandled_exception_handler,
)
from infra.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from infra.config.database import settings, engine
from domain.entities import Base
from interfaces.api.auth_router import router as auth_router
from interfaces.api.org_router import router as org_router, plans_router
from interfaces.api.brand_router import router as brand_router
from interfaces.api.product_router import router as product_router
from interfaces.api.agent_router import config_router as agent_config_router, task_router as agent_task_router
from interfaces.api.flow_router import router as flow_router
from interfaces.api.agent_execute_router import router as agent_execute_router
from interfaces.api.creative_router import router as creative_router
from interfaces.api.landing_page_router import router as landing_page_router
from interfaces.api.orchestrator_router import router as orchestrator_router
from interfaces.api.flow_execute_router import router as flow_execute_router
from interfaces.api.flow_template_router import router as flow_template_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Error handlers (orden importa: más específico primero)
app.add_exception_handler(NexOSError, nexos_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Request context middleware (request_id + logging)
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(org_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")
app.include_router(brand_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")
app.include_router(agent_config_router, prefix="/api/v1")
app.include_router(agent_task_router, prefix="/api/v1")
app.include_router(flow_router, prefix="/api/v1")
app.include_router(agent_execute_router, prefix="/api/v1")
app.include_router(creative_router, prefix="/api/v1")
app.include_router(landing_page_router, prefix="/api/v1")
app.include_router(orchestrator_router, prefix="/api/v1")
app.include_router(flow_execute_router, prefix="/api/v1")
app.include_router(flow_template_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}