import json
import shutil
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, create_autospec
from uuid import UUID

import pytest
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import create_engine
from src.api.dependencies.auth import (
    AuthenticationState,
    _get_auth_token,
    authenticated,
)
from src.api.dependencies.sandboxed_functions import ValidateModalFileProvider, DeployModalAppProvider
from src.api.dependencies.sandboxed_functions import validate_modal_file, deploy_modal_app
from src.config import Settings, get_settings
from src.main import app
from src.models.base import Base
from testcontainers.postgres import PostgresContainer


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
def mock_db_session(
    override_get_settings_dependency,
    mock_settings,
):
    """override_get_settings_dependency gives get_db_session the url of the database.
    To make sure tests don't interfere with each other we first need to initialize the schema,
    then let the test run and drop the schema after the test.
    """
    url = mock_settings.SQLALCHEMY_DATABASE_URL
    if "postgres" not in url:
        raise ValueError(
            f"Can only run integration tests against postgres, got: {url} "
            'Try `pytest -m "not integration"`'
        )

    # create synchronous engine so we can drop and rebuild the schema between tests
    sync_url = url.replace("asyncpg", "psycopg2")
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def mock_validate_modal_file():
    mock_validate_modal_file = MagicMock(spec=validate_modal_file)
    return mock_validate_modal_file


@pytest.fixture
def mock_deploy_modal_app():
    mock_deploy_modal_app = MagicMock(spec=deploy_modal_app)
    return mock_deploy_modal_app


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


def create_mock_provider(provider_class):
    # Create an instance of a provider class used to inject a Modal function as a dependency
    provider_instance = provider_class()
    
    # Create an autospec of the __call__ method
    mocked_call = create_autospec(provider_instance.__call__, side_effect=lambda *args, **kwargs: None)
    
    # Create a new class that mimics the original provider
    class MockProvider:
        def __call__(self, *args, **kwargs):
            return mocked_call(*args, **kwargs)

    return MockProvider()


@pytest.fixture
def mock_validate_modal_file_provider():
    return create_mock_provider(ValidateModalFileProvider)


@pytest.fixture
def mock_deploy_modal_app_provider():
    return create_mock_provider(DeployModalAppProvider)


@pytest.fixture
def override_validate_modal_file_dependency(mock_validate_modal_file_provider):
    app.dependency_overrides[ValidateModalFileProvider] = lambda: mock_validate_modal_file_provider
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_deploy_modal_app_dependency(mock_deploy_modal_app_provider):
    app.dependency_overrides[DeployModalAppProvider] = lambda: mock_deploy_modal_app_provider
    yield
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
def create_shared_entrypoint_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-shared-entrypoint.json"
    )
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
