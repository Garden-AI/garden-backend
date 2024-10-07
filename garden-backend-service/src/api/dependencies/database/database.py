from pathlib import Path

import sqlparse
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings


async def init(db_session: async_sessionmaker):
    """Initialize the database with custom SQL"""
    custom_sql = Path(f"{__file__}").parent / "sql.sql"

    with open(custom_sql, "r") as f:
        raw_sql = f.read()
    statements = sqlparse.split(raw_sql)

    async with db_session() as db:
        for stmt in statements:
            await db.execute(text(stmt))


async def get_db_session(settings=Depends(get_settings)) -> AsyncSession:
    """Get the database session then close it after the request is complete."""
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db_session:
        yield db_session
