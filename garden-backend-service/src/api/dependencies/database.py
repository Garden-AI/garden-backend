from pathlib import Path

import sqlparse
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from src.config import get_settings


async def async_init(db_session: async_sessionmaker, sql_path: Path):
    """Initialize the database with custom SQL"""
    with open(sql_path, "r") as f:
        raw_sql = f.read()
    statements = sqlparse.split(raw_sql)
    async with db_session() as db:
        for stmt in statements:
            await db.execute(text(stmt))
        await db.commit()


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
