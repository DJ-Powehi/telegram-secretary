"""
Database connection and session management.
Supports both SQLite (local) and PostgreSQL (production).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from config import get_config

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_async_session_factory = None


def _convert_database_url(url: str) -> str:
    """Convert database URL to async format."""
    # SQLite
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    # PostgreSQL
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _is_sqlite(url: str) -> bool:
    """Check if URL is for SQLite database."""
    return "sqlite" in url.lower()


async def init_database() -> None:
    """Initialize the database connection pool."""
    global _engine, _async_session_factory
    
    config = get_config()
    async_url = _convert_database_url(config.database.url)
    is_sqlite = _is_sqlite(async_url)
    
    # SQLite needs different settings
    if is_sqlite:
        _engine = create_async_engine(
            async_url,
            poolclass=StaticPool,  # Required for SQLite async
            echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        _engine = create_async_engine(
            async_url,
            poolclass=NullPool,  # Better for Railway's connection handling
            echo=False,
        )
    
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    db_type = "SQLite" if is_sqlite else "PostgreSQL"
    logger.info(f"{db_type} database connection initialized")


async def close_database() -> None:
    """Close the database connection pool."""
    global _engine
    
    if _engine:
        await _engine.dispose()
        logger.info("Database connection pool closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables defined in models."""
    from models import Base
    
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")

