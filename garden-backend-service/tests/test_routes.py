import pytest
import requests
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app
from src.config import Settings, get_settings
from src.api.dependencies.auth import authenticated, AuthenticationState


client = TestClient(app)


@pytest.fixture
def mock_auth_state():
    # Mock auth state for authenticated user
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Monsieur Sartre"
    return mock_auth


@pytest.fixture(autouse=True)
def mock_boto3_get_secret_value():
    # Typical secret response format
    mock_secret_value_response = {
        "ARN": "arn:aws:secretsmanager:us-east-1:1234567890:secret:test",
        "Name": "test",
        "VersionId": "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111",
        "SecretString": '{"DATACITE_PREFIX": "PREFIX", "DATACITE_ENDPOINT": "ENDPOINT", "DATACITE_REPO_ID": "REPO_ID", "DATACITE_PASSWORD": "PASSWORD"}',
        "VersionStages": ["AWSCURRENT"],
        "CreatedDate": "2021-01-22T21:46:32.725000+08:00",
    }
    with patch("boto3.session.Session.client") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.get_secret_value.return_value = mock_secret_value_response
        yield


@pytest.fixture
def mock_settings():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.DATACITE_PREFIX = "PREFIX"
    mock_settings.DATACITE_ENDPOINT = "http://localhost:8000"
    mock_settings.DATACITE_REPO_ID = "REPO_ID"
    mock_settings.DATACITE_PASSWORD = "PASSWORD"
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


def test_greet_world():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello there": "You must be World"}


def test_greet_authed_user(override_authenticated_dependency):
    response = client.get("/greet/")
    assert response.status_code == 200
    assert response.json() == {
        "Welcome, Monsieur Sartre": "you're looking very... authentic today."
    }


def test_missing_auth_header():
    response = client.get("/greet/")
    assert response.status_code == 403
    assert response.json() == {"detail": "Authorization header missing"}


@patch("requests.post", autospec=True)
def test_mint_draft_doi(
    mock_post,
    mock_auth_state,
    mock_settings,
    override_authenticated_dependency,
    override_get_settings_dependency,
):
    mock_request_body = {"data": {"type": "dois", "attributes": {}}}
    mock_response_body = {
        "data": {"type": "dois", "attributes": {"doi": "10.fake/doi"}}
    }

    mock_post.return_value.json.return_value = mock_response_body
    mock_post.return_value.raise_for_status.return_value = None

    response = client.post("/doi", json=mock_request_body)

    assert response.status_code == 201
    assert response.json() == {"doi": "10.fake/doi"}


@patch("requests.put", autospec=True)
def test_update_datacite(
    mock_put,
    mock_auth_state,
    mock_settings,
    override_authenticated_dependency,
    override_get_settings_dependency,
):
    mock_request_body = {
        "data": {
            "type": "dois",
            "attributes": {
                "identifiers": [{"identifier": "10.fake/doi"}],
                "event": "publish",
                "url": "https://thegardens.ai/10.fake/doi",
            },
        }
    }
    mock_put.return_value.json.return_value = mock_request_body
    mock_put.return_value.raise_for_status.return_value = None

    response = client.put("/doi", json=mock_request_body)

    assert response.status_code == 200
    assert response.json() == mock_request_body
