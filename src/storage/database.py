from src.models.schema import Base
from src.core.config import settings
from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Automatically add missing job_configs columns if they don't exist
        await conn.execute(text("ALTER TABLE job_configs ADD COLUMN IF NOT EXISTS volume_threshold INTEGER NULL"))
        await conn.execute(text("ALTER TABLE job_configs ADD COLUMN IF NOT EXISTS cooldown_minutes INTEGER NOT NULL DEFAULT 5"))


async def close_db() -> None:
    await engine.dispose()