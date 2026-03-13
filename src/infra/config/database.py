from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., description="PostgreSQL async connection string")
    APP_NAME: str = Field(default="NexOS")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session