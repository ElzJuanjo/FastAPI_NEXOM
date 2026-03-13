from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infra.config.database import settings, engine
from domain.entities.base import Base
from interfaces.api.auth_router import router as auth_router
from interfaces.api.org_router import router as org_router, plans_router
from interfaces.api.brand_router import router as brand_router
from interfaces.api.product_router import router as product_router
from interfaces.api.agent_router import config_router as agent_config_router, task_router as agent_task_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}