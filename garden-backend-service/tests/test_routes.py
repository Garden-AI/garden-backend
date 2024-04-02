import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.main import app
from src.api.dependencies.auth import authenticated, AuthenticationState

client = TestClient(app)


@pytest.fixture
def mock_auth_state():
    # Mock auth state for authenticated user
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Monsieur Sartre"
    return mock_auth


@pytest.fixture
def override_authenticated_dependency(mock_auth_state):
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
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
