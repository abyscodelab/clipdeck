"""Async SQLAlchemy database setup supporting SQLite and Supabase PostgreSQL."""

import re
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_db_url = settings.DATABASE_URL
connect_args: dict = {}
engine_kwargs: dict = {"echo": settings.DEBUG}

if _db_url.startswith("sqlite://"):
    _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    connect_args["check_same_thread"] = False
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Handle Supabase Postgres / asyncpg SSL and pooling parameters
if "postgresql+asyncpg" in _db_url:
    if "sslmode=" in _db_url:
        _db_url = re.sub(r"[?&]sslmode=[^&]+", "", _db_url)
    connect_args["ssl"] = "require"
    # Essential for Supabase PgBouncer pooler (port 6543)
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    })

engine = create_async_engine(
    _db_url,
    connect_args=connect_args,
    **engine_kwargs,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        import app.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
