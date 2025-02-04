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


class DatabaseEngine:
    """A singleton class to manage database engine and session maker instances."""

    _instance = None
    _engine: AsyncEngine | None = None
    _async_session_maker: async_sessionmaker[AsyncSession] | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DatabaseEngine":
        """Get the singleton instance of DatabaseEngine."""
        return cls()

    def get_engine(self, postgres_url: str) -> AsyncEngine:
        """Get or create the singleton database engine."""
        if self._engine is None:
            self._engine = create_async_engine(
                postgres_url,
                echo=False,
            )
        return self._engine

    def get_session_maker(
        self, engine: AsyncEngine
    ) -> async_sessionmaker[AsyncSession]:
        """Get or create the singleton session maker."""
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_maker

    def dispose(self) -> None:
        """Dispose of the engine and session maker. Mainly useful for testing."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
        self._async_session_maker = None


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
    session_maker = await get_db_session_maker(settings)
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_session_maker(
    settings=Depends(get_settings),
) -> async_sessionmaker[AsyncSession]:
    """Get the singleton session maker instance."""
    db_engine = DatabaseEngine.get_instance()
    engine = db_engine.get_engine(settings.SQLALCHEMY_DATABASE_URL)
    return db_engine.get_session_maker(engine)
