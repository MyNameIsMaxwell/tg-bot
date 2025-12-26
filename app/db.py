"""Database setup using SQLAlchemy async engine."""

import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


# SQLite-specific configuration for better concurrency handling
_connect_args = {}
_extra_engine_args = {}

if settings.database_url.startswith("sqlite"):
    # Add busy timeout (30 seconds) to handle concurrent access
    # and enable WAL mode for better concurrency
    _connect_args = {
        "timeout": 30,  # Wait up to 30 seconds when database is locked
        "check_same_thread": False,
        "isolation_level": None,  # Use autocommit for aiosqlite
    }
    # Use NullPool for async SQLite - creates new connection per session
    # This avoids connection sharing issues between async tasks
    _extra_engine_args = {
        "poolclass": NullPool,
    }

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    **_extra_engine_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync() -> None:
    """Helper for running init_db in sync contexts (tests, scripts)."""
    asyncio.run(init_db())



