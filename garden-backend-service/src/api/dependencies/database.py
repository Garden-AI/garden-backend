from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.config import get_settings

postgres_url = get_settings().SQLALCHEMY_DATABASE_URL
engine = create_engine(postgres_url, echo=True)
SessionLocal = sessionmaker(bind=engine)

# lifted from funcx web service in case we decide we need it
_async_url = postgres_url.replace("://", "+asyncpg://")
_async_engine = create_async_engine(_async_url, echo=True)
_SessionLocalAsync = sessionmaker(bind=_async_engine, class_=AsyncSession)


def get_db_session() -> SessionLocal:
    """Get the database session then close it after the request is complete."""

    with SessionLocal() as db_session:
        yield db_session
