"""
Async SQLAlchemy session factory for the Store Intelligence System.

Supports both PostgreSQL (production) and SQLite (development/testing).
Provides:
  - init_db()  → create engine + tables
  - close_db() → dispose engine
  - get_db     → FastAPI dependency yielding async session
"""

import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Global engine and session factory
_engine = None
_async_session_factory = None


def _get_database_url() -> str:
    """Get database URL from environment, defaulting to SQLite for dev."""
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    return url


def _get_engine_kwargs(url: str) -> dict:
    """Get engine kwargs based on database type."""
    kwargs = {"echo": False}
    if "sqlite" in url:
        # SQLite needs check_same_thread=False for async
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL connection pool settings
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True
    return kwargs


async def init_db():
    """
    Initialize the database engine and create all tables.
    Called during FastAPI lifespan startup.
    """
    global _engine, _async_session_factory

    url = _get_database_url()
    kwargs = _get_engine_kwargs(url)
    _engine = create_async_engine(url, **kwargs)

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create all tables
    from app.models.db import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Dispose the database engine.
    Called during FastAPI lifespan shutdown.
    """
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


async def get_db():
    """
    FastAPI dependency that yields an async database session.
    Usage: db = Depends(get_db)
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_engine():
    """Get the current engine (for health checks)."""
    return _engine


def get_session_factory():
    """Get the session factory (for background tasks)."""
    return _async_session_factory
