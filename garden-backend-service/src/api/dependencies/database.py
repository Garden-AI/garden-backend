from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import get_settings

postgres_url = get_settings().SQLALCHEMY_DATABASE_URL

engine = create_engine(postgres_url, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> SessionLocal:
    """Get the database session then close it after the request is complete."""

    with SessionLocal() as db_session:
        yield db_session
