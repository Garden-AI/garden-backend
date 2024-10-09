import json
import shutil
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from src.api.dependencies.auth import (
    AuthenticationState,
    _get_auth_token,
    authenticated,
    modal_vip,
)
from src.api.dependencies.database import init
from src.api.dependencies.modal import get_modal_client
from src.api.dependencies.sandboxed_functions import (
    DeployModalAppProvider,
    ValidateModalFileProvider,
)
from src.config import Settings, get_settings
from src.main import app
from src.models.base import Base


@pytest.fixture
def client(patch_globus_groups):
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client


@pytest.fixture
def patch_globus_groups(mocker):
    mocker.patch("src.api.dependencies.auth.add_user_to_group")


def docker_available():
    available = shutil.which("docker")
    return available


def pytest_collection_modifyitems(session, config, items):
    """Skip integration tests that rely on docker if docker is not available"""
    if not docker_available():
        skip_marker = pytest.mark.skip(
            reason="Unable to run integration tests: Docker is not available"
        )
        for item in items:
            if "mock_db_session" in item.fixturenames:
                item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def pg_container() -> Optional[PostgresContainer]:
    if docker_available():
        with PostgresContainer("postgres:16", driver="asyncpg") as postgres:
            yield postgres
    else:
        yield None


@pytest.fixture(scope="session")
def db_url(pg_container) -> str:
    if pg_container:
        return pg_container.get_connection_url()
    else:
        return "No database available."


@pytest.fixture
def _sync_engine(mock_settings):
    url = mock_settings.SQLALCHEMY_DATABASE_URL
    if "postgres" not in url:
        raise ValueError(
            f"Can only run integration tests against postgres, got: {url} "
            'Try `pytest -m "not integration"`'
        )
    sync_url = url.replace("asyncpg", "psycopg2")
    engine = create_engine(sync_url)
    yield engine
    engine.dispose()


@pytest.fixture
def mock_db_session(
    mock_settings,
    override_get_settings_dependency,
    _sync_engine,
):
    """Provide a mock database session to the test.

    override_get_settings_dependency gives get_db_session the url of the database
    so routes that need the database will automatically be given the url of the test db.
    """
    # Initialize the database schema
    Base.metadata.create_all(_sync_engine)
    with Session(_sync_engine) as db:
        init(db, Path(mock_settings.GARDEN_SEARCH_SQL_DIR))

    # Let the test use the database
    yield

    # Clean up after the test
    with Session(_sync_engine) as db:
        db.execute(text("DROP TABLE gardens_entrypoints;"))
        db.execute(text("DROP TABLE entrypoints CASCADE;"))
        db.execute(text("DROP TABLE gardens CASCADE;"))
        db.execute(text("DROP TABLE users CASCADE;"))
        db.execute(text("DROP TABLE failed_search_index_updates CASCADE;"))
        db.commit()


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


@pytest.fixture
def override_get_settings_dependency_with_sync(mock_settings_with_sync):
    app.dependency_overrides[get_settings] = lambda: mock_settings_with_sync
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_validate_modal_file_provider():
    mock_provider = MagicMock(spec=ValidateModalFileProvider)
    mock_provider.return_value = {
        "app_name": "my-modal-app",
        "function_names": ["predict_iris_type"],
    }
    return mock_provider


@pytest.fixture
def mock_deploy_modal_app_provider():
    return MagicMock(spec=DeployModalAppProvider)


@pytest.fixture
def override_validate_modal_file_dependency(mock_validate_modal_file_provider):
    app.dependency_overrides[ValidateModalFileProvider] = (
        lambda: mock_validate_modal_file_provider
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_deploy_modal_app_dependency(mock_deploy_modal_app_provider):
    app.dependency_overrides[DeployModalAppProvider] = (
        lambda: mock_deploy_modal_app_provider
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_modal_vip():
    app.dependency_overrides[modal_vip] = lambda: True
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_get_modal_client_dependency():
    mock_modal_client = AsyncMock()
    mock_modal_client.stub = MagicMock()
    app.dependency_overrides[get_modal_client] = lambda: mock_modal_client
    yield mock_modal_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth_state():
    # Mock auth state for authentic user
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Monsieur.Sartre@ens-paris.fr"
    mock_auth.identity_id = UUID("00000000-0000-0000-0000-000000000000")
    mock_auth.token = "tokentokentoken"
    mock_auth.email = "some@email.com"
    mock_auth.name = "M. Sartre"
    return mock_auth


@pytest.fixture
def mock_auth_state_other_user():
    # this one's a joke about The Other
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Madame.deBeauvoir@ens-paris.fr"
    mock_auth.identity_id = UUID("10101010-1010-1010-1010-101010101010")
    mock_auth.token = "tokentokentoken"
    mock_auth.email = "simone.debeauvoir@ens-paris.fr"
    mock_auth.name = "Mme. de Beauvoir"
    return mock_auth


@pytest.fixture
def mock_missing_token():
    def missing_auth_token_effect(authorization=Depends(HTTPBearer(auto_error=False))):
        raise HTTPException(status_code=403, detail="Authorization header missing")

    app.dependency_overrides[_get_auth_token] = missing_auth_token_effect
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_settings(db_url):
    mock_settings = MagicMock(spec=Settings)
    mock_settings.DATACITE_PREFIX = "PREFIX"
    mock_settings.DATACITE_ENDPOINT = "http://localhost:8000"
    mock_settings.DATACITE_REPO_ID = "REPO_ID"
    mock_settings.DATACITE_PASSWORD = "PASSWORD"
    mock_settings.ECR_REPO_ARN = "ECR_REPO_ARN"
    mock_settings.ECR_ROLE_ARN = "ECR_ROLE_ARN"
    mock_settings.STS_TOKEN_TIMEOUT = 1234
    mock_settings.NOTEBOOKS_S3_BUCKET = "test-bucket"
    mock_settings.SQLALCHEMY_DATABASE_URL = db_url
    mock_settings.GARDEN_USERS_GROUP_ID = "fakeid"
    mock_settings.SYNC_SEARCH_INDEX = False
    mock_settings.GLOBUS_SEARCH_INDEX_ID = "GLOBUS_ID"
    mock_settings.API_CLIENT_ID = "fakeid"
    mock_settings.API_CLIENT_SECRET = "secretfakeid"
    mock_settings.RETRY_INTERVAL_SECS = 1
    mock_settings.MDF_SEARCH_INDEX = "mdfsearchindex"
    mock_settings.MODAL_ENV = "dev"
    mock_settings.MODAL_TOKEN_ID = "fake-token-id"
    mock_settings.MODAL_TOKEN_SECRET = "fake-token-secret"
    mock_settings.MODAL_USE_LOCAL = True
    mock_settings.MODAL_ENABLED = True
    mock_settings.GARDEN_SEARCH_SQL_DIR = "src/api/search/sql.sql"
    mock_settings.MODAL_VIP_LIST = []
    return mock_settings


@pytest.fixture
def mock_settings_with_sync(mock_settings):
    mock_settings.SYNC_SEARCH_INDEX = True
    return mock_settings


@pytest.fixture
def create_entrypoint_with_related_metadata_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-with-metadata.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_entrypoint_archived_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "EntrypointCreateRequest-archived.json"
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_published_entrypoint_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "EntrypointCreateRequest-published.json"
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_shared_entrypoint_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-shared-entrypoint.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_published_garden_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "GardenCreateRequest-published.json"
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_garden_two_entrypoints_json() -> dict:
    """Request payload to create a garden referencing two other entrypoints by DOI.
    Note: Trying to create the garden before these entrypoints exist in the DB will cause an error.
    See:  create_entrypoint_with_related_metadata_json, create_shared_entrypoint_json
    """
    path = (
        Path(__file__).parent / "fixtures" / "GardenCreateRequest-two-entrypoints.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def create_garden_shares_entrypoint_json() -> dict:
    """Request payload to create a garden referencing one of another garden's entrypoints.
    See: create_garden_two_entrypoints_json, create_shared_entrypoint_json
    """
    path = (
        Path(__file__).parent
        / "fixtures"
        / "GardenCreateRequest-shares-entrypoint.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def mock_garden_create_request_archived_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "GardenCreateRequest-archived.json"
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def mock_entrypoint_create_request_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-with-metadata.json"
    )
    assert path.exists()
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def mock_garden_create_request_no_entrypoints_json() -> dict:
    path = (
        Path(__file__).parent / "fixtures" / "GardenCreateRequest-no-entrypoints.json"
    )
    assert path.exists()
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture
def mock_modal_app_create_request_one_function() -> dict:
    path = (
        Path(__file__).parent / "fixtures" / "ModalAppCreateRequest-one-function.json"
    )
    assert path.exists()
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture(autouse=True)
def mock_is_doi_registered(mocker):
    mock_garden = mocker.patch("src.api.routes.gardens.is_doi_registered")
    mock_garden.return_value = False

    return mock_garden
