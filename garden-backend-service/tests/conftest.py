import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from httpx import ASGITransport, AsyncClient
from modal_proto import api_pb2
from sqlalchemy import NullPool, text
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from src.api.dependencies.auth import (
    AuthenticationState,
    _get_auth_token,
    authenticated,
    in_modal_publishers_group,
    under_modal_usage_limit,
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


def pytest_addoption(parser):
    parser.addoption(
        "--num-concurrent-requests",
        type=int,
        default=os.getenv("GARDEN_TEST_NUM_CONCURRENT_REQUESTS", 30),
        help="Number of concurrent requests to run in load tests.",
    )


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
    mocker,
):
    """Provide a mock database session to the test.

    override_get_settings_dependency gives get_db_session the url of the database
    so routes that need the database will automatically be given the url of the test db.
    """
    # Initialize the database schema
    Base.metadata.create_all(_sync_engine)
    with Session(_sync_engine) as db:
        init(db, Path(mock_settings.GARDEN_SEARCH_SQL_DIR))

    # NullPool fixes an issue where the engine connections are reused between tests
    # and the tests interfere with each other. This doesn't happen in the real app,
    #  I think it has something to do with pytest's async setup
    def _create_async_engine(a, b):
        # a and b are ignored, they are just placeholders for the arguments
        return create_async_engine(
            mock_settings.SQLALCHEMY_DATABASE_URL, poolclass=NullPool
        )  # null pool is needed to avoid connections being reused

    mocker.patch(
        "src.api.dependencies.database.DatabaseEngine.get_engine", _create_async_engine
    )

    # Let the test use the database
    yield

    # Clean up after the test
    with Session(_sync_engine) as db:
        db.execute(text("DROP MATERIALIZED VIEW garden_documents;"))
        db.execute(text("DROP MATERIALIZED VIEW entrypoint_documents;"))
        db.execute(text("DROP MATERIALIZED VIEW modal_function_documents;"))
        db.commit()
    Base.metadata.drop_all(_sync_engine)


@pytest.fixture
def override_authenticated_dependency(mock_auth_state):
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_publisher_group_membership():
    app.dependency_overrides[in_modal_publishers_group] = lambda: True
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_modal_publisher_auth_state(
    override_authenticated_dependency,
    override_publisher_group_membership,
    mock_auth_state,
):
    """Gives mock auth state and overrides the relevant auth checks"""
    return mock_auth_state


@pytest.fixture
def override_get_settings_dependency(mock_settings):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_usage_limit_dependency():
    async def mock_usage_limit():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is over Modal usage limit for the month.",
        )

    app.dependency_overrides[under_modal_usage_limit] = mock_usage_limit
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_validate_modal_file_provider(request):
    mock_provider = AsyncMock(spec=ValidateModalFileProvider)
    mock_provider.return_value = getattr(request, "param", None) or {
        "app_name": "test-app",
        "functions": {"predict_iris_type": {"cpus": 1, "gpus": "A100", "memory": 256}},
    }
    return mock_provider


@pytest.fixture
def mock_deploy_modal_app_provider():
    return AsyncMock(
        spec=DeployModalAppProvider, return_value={"app_id": "ap-fakeappid"}
    )


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
def override_sandboxed_functions(
    override_deploy_modal_app_dependency, override_validate_modal_file_dependency
):
    return


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
    mock_settings.GARDEN_SEARCH_SQL_DIR = "src/api/search/sql.sql"
    mock_settings.MODAL_USAGE_LIMIT = 5.0
    mock_settings.MODAL_TIMEOUT_SECONDS = 10.0
    mock_settings.SUPER_USERS = [
        "c8741264-d274-11e5-bee7-f30dff9f1ea8",  # Ben
        "6c9e223f-c215-4c26-9abb-262dbce0001c",  # Will
        "76024960-c68b-4fec-8cb8-b65b096f18da",  # Owen
        "e9a17e09-657b-4087-a719-241ab72b1d9b",  # Hayden
    ]
    return mock_settings


@pytest.fixture
def num_concurrent_requests(request):
    return request.config.getoption("--num-concurrent-requests")


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


@pytest.fixture
def mock_modal_app_create_request_with_class() -> dict:
    path = Path(__file__).parent / "fixtures" / "ModalAppCreateRequest-class.json"
    assert path.exists()
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture(autouse=True)
def mock_is_doi_registered(mocker):
    mock_garden = mocker.patch("src.api.routes.gardens.is_doi_registered")
    mock_garden.return_value = False

    return mock_garden


@pytest.fixture
def mock_modal_function() -> MagicMock:
    """Fixture for mocking a Modal function"""
    mock_function = MagicMock()
    mock_function._invocation_function_id.return_value = "mock_function_id"
    mock_function.spec.return_value = {"cpu": 0.125, "gpus": "A100", "memory": None}
    return mock_function


@pytest.fixture
def mock_modal_invocation() -> AsyncMock:
    """Fixture for mocking a Modal invocation with successful result"""
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "mock_call_id"
    # Mock successful output
    mock_invocation.pop_function_call_outputs.return_value = MagicMock(
        outputs=[
            api_pb2.FunctionGetOutputsItem(
                result=api_pb2.GenericResult(
                    status=api_pb2.GenericResult.GENERIC_STATUS_SUCCESS,
                    data=b"mock_result",
                ),
                data_format=api_pb2.DATA_FORMAT_PICKLE,
            )
        ]
    )
    return mock_invocation


@pytest.fixture
def modal_test_environment(
    client: AsyncClient,
    mocker,
    mock_modal_function,
    mock_modal_invocation,
    override_publisher_group_membership,
    override_authenticated_dependency,
    override_sandboxed_functions,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mock_db_session,
    mock_auth_state,
):
    """Composite fixture that sets up all dependencies needed for Modal testing.

    This combines the most commonly used fixtures for Modal-related tests into a single fixture.
    Returns a dictionary containing the initialized test client and other useful test objects.
    """
    return {
        "client": client,
        "mocker": mocker,
        "mock_function": mock_modal_function,
        "mock_invocation": mock_modal_invocation,
        "auth_state": mock_auth_state,
        "modal_client": override_get_modal_client_dependency,
    }


@pytest.fixture
def modal_deployment_environment(
    modal_test_environment: dict[str, Any],
    mock_modal_app_create_request_one_function: dict[str, Any],
):
    """Composite fixture specifically for Modal deployment tests.

    Extends modal_test_environment with deployment-specific fixtures and configuration.
    """
    return {
        **modal_test_environment,
        "app_request": mock_modal_app_create_request_one_function,
    }
