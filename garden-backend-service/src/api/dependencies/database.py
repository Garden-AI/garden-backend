from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from src.config import get_settings


async def get_db_session(settings=Depends(get_settings)) -> AsyncSession:
    """Get the database session then close it after the request is complete."""
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=True)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession)

    async with SessionLocal() as db_session:
        yield db_session
