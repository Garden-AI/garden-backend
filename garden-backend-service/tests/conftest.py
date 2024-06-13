import json
from pathlib import Path

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
from unittest.mock import MagicMock
from uuid import UUID

from src.api.dependencies.auth import (
    AuthenticationState,
    authenticated,
    _get_auth_token,
)
from src.api.dependencies.database import get_db_session

from src.config import Settings, get_settings
from src.main import app
from src.models.base import Base


@pytest.fixture(scope="session")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:16") as postgres:
        yield postgres


@pytest.fixture
async def mock_db_session(pg_container):
    url = pg_container.get_connection_url()
    async_url = url.replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def override_get_db_session_dependency(mock_db_session):
    async def _get_test_db():
        async for session in mock_db_session:
            yield session

    app.dependency_overrides[get_db_session] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def mock_entrypoint_create_request_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "EntrypointCreateRequest.json"
    assert path.exists()
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def mock_auth_state():
    # Mock auth state for authentic user
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Monsieur.Sartre@ens-paris.fr"
    mock_auth.identity_id = UUID("00000000-0000-0000-0000-000000000000")
    mock_auth.token = "tokentokentoken"
    return mock_auth


@pytest.fixture
def mock_missing_token():
    def missing_auth_token_effect(authorization=Depends(HTTPBearer(auto_error=False))):
        raise HTTPException(status_code=403, detail="Authorization header missing")

    app.dependency_overrides[_get_auth_token] = missing_auth_token_effect
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_settings():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.DATACITE_PREFIX = "PREFIX"
    mock_settings.DATACITE_ENDPOINT = "http://localhost:8000"
    mock_settings.DATACITE_REPO_ID = "REPO_ID"
    mock_settings.DATACITE_PASSWORD = "PASSWORD"
    mock_settings.ECR_REPO_ARN = "ECR_REPO_ARN"
    mock_settings.ECR_ROLE_ARN = "ECR_ROLE_ARN"
    mock_settings.STS_TOKEN_TIMEOUT = 1234
    mock_settings.NOTEBOOKS_S3_BUCKET = "test-bucket"
    mock_settings.SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    return mock_settings


@pytest.fixture
def override_authenticated_dependency(mock_auth_state):
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_get_settings_dependency(mock_settings):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield
    app.dependency_overrides.clear()
