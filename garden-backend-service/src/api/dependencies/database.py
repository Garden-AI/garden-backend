from contextlib import asynccontextmanager
from pathlib import Path

import sqlparse
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from structlog import get_logger

from src.config import get_settings

log = get_logger(__name__)

SEARCH_SQL_INIT_LOCK_ID = 20250117  # YYYYMMDD when implemented


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


async def async_init(db_session: async_sessionmaker, sql_path: Path):
    """Initialize the database with custom SQL"""
    with open(sql_path, "r") as f:
        raw_sql = f.read()
    statements = sqlparse.split(raw_sql)

    async with db_session() as db:
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


async def get_db_session(settings=Depends(get_settings)) -> AsyncSession:
    """Get the database session then close it after the request is complete."""
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db_session:
        yield db_session


async def get_db_session_maker(settings=Depends(get_settings)) -> async_sessionmaker:
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=False)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
