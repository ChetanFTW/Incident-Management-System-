import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def init_db():
    """Create all tables with retry — handles DB not-ready-yet on cold start."""
    async with engine.begin() as conn:
        from app.models import pg_models  # noqa: F401 — registers models with Base
        await conn.run_sync(Base.metadata.create_all)
        # TimescaleDB hypertable for signal aggregations
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS signal_timeseries (
                time         TIMESTAMPTZ NOT NULL,
                component_id TEXT NOT NULL,
                severity     TEXT NOT NULL,
                count        INTEGER DEFAULT 1
            )
        """))
        try:
            await conn.execute(text(
                "SELECT create_hypertable('signal_timeseries','time',if_not_exists=>TRUE)"
            ))
        except Exception:
            pass  # already a hypertable
    logger.info("PostgreSQL ready")


async def close_db():
    await engine.dispose()


async def get_pg_status() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
