from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import sqlparse
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from structlog import get_logger

from src.config import get_settings

log = get_logger(__name__)

SEARCH_SQL_INIT_LOCK_ID = 20250117  # YYYYMMDD when implemented

# Global engine instance
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine(postgres_url: str) -> AsyncEngine:
    """Get or create the singleton database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            postgres_url, echo=False, pool_size=20, max_overflow=10
        )
    return _engine


def get_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Get or create the singleton session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Get a database session from the session maker."""
    session_maker = get_session_maker(
        get_engine(get_settings().SQLALCHEMY_DATABASE_URL)
    )
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def advisory_lock(db: AsyncSession):
    """Manage a Postgres advisory lock in an async context

    Usage:
        async with advisory_lock(db, DBLock.SEARCH_SQL_INIT) as locked:
            if locked:
                # Do protected operations
    """
    # Try to acquire lock without waiting
    result = await db.execute(
        text(f"SELECT pg_try_advisory_lock({SEARCH_SQL_INIT_LOCK_ID})")
    )
    lock_acquired = result.scalar()
    try:
        yield lock_acquired
    finally:
        if lock_acquired:
            await db.execute(
                text(f"SELECT pg_advisory_unlock({SEARCH_SQL_INIT_LOCK_ID})")
            )


async def async_init(
    session_maker: async_sessionmaker[AsyncSession], sql_path: Path
) -> None:
    """Initialize the database with custom SQL"""
    with open(sql_path, "r") as f:
        raw_sql = f.read()
    statements = sqlparse.split(raw_sql)

    async with session_maker() as db:
        async with advisory_lock(db) as locked:
            if not locked:
                log.debug("Search SQL initialization already in progress")
                return

            for stmt in statements:
                await db.execute(text(stmt))
            await db.commit()
            log.info("Search SQL initialization completed successfully")


def init(db: Session, sql_path: Path):
    with open(sql_path, "r") as f:
        raw_sql = f.read()
    statements = sqlparse.split(raw_sql)
    for stmt in statements:
        db.execute(text(stmt))
    db.commit()


async def get_db_session(
    settings=Depends(get_settings),
) -> AsyncIterator[AsyncSession]:
    """Get a database session from the singleton session maker."""
    async with get_session() as session:
        yield session


async def get_db_session_maker(
    settings=Depends(get_settings),
) -> async_sessionmaker[AsyncSession]:
    """Get the singleton session maker instance."""
    engine = get_engine(settings.SQLALCHEMY_DATABASE_URL)
    return get_session_maker(engine)
