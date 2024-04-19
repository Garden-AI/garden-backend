import pytest
import requests
import hashlib
import json
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app
from src.config import Settings, get_settings
from src.api.dependencies.auth import authenticated, AuthenticationState
from src.api.schemas.notebook import UploadNotebookRequest, UploadNotebookResponse


client = TestClient(app)


@pytest.fixture
def mock_auth_state():
    # Mock auth state for authenticated user
    mock_auth = MagicMock(spec=AuthenticationState)
    mock_auth.username = "Monsieur.Sartre@ens-paris.fr"
    return mock_auth


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
        "Welcome, Monsieur.Sartre@ens-paris.fr": "you're looking very... authentic today."
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


def test_get_push_session(
    override_get_settings_dependency, override_authenticated_dependency
):
    mock_assume_role = {
        "Credentials": {
            "AccessKeyId": "testAccessKey",
            "SecretAccessKey": "testSecretKey",
            "SessionToken": "testSessionToken",
        }
    }

    with patch("boto3.client") as mock_client:
        client_instance = mock_client.return_value
        client_instance.assume_role.return_value = mock_assume_role

        response = client.get("/docker-push-token/")

    assert response.status_code == 200
    assert response.json() == {
        "AccessKeyId": "testAccessKey",
        "SecretAccessKey": "testSecretKey",
        "SessionToken": "testSessionToken",
        "ECRRepo": "ECR_REPO_ARN",
        "RegionName": "us-east-1",
    }

    for key in ["AccessKeyId", "SecretAccessKey", "SessionToken", "ECRRepo"]:
        assert key in response.json()


def test_upload_notebook(
    override_authenticated_dependency, override_get_settings_dependency
):
    request_data = dict(
        notebook_name="test_notebook",
        notebook_json=json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "interlinked",
                        "within_cells": "interlinked",
                        "source": "print('dreadfully distinct')",
                    }
                ]
            }
        ),
        folder="Monsieur.Sartre@ens-paris.fr",  # not a commentary on nabokov, just needs to match the auth mock lol
    )
    request_obj = UploadNotebookRequest(**request_data)
    test_hash = hashlib.sha256(request_obj.json().encode()).hexdigest()

    with patch("boto3.client") as mock_boto_client:
        mock_s3 = mock_boto_client.return_value
        response = client.post("/notebook/", json=request_data)

        assert response.status_code == 200
        assert (
            "test-bucket.s3.amazonaws.com/Monsieur.Sartre@ens-paris.fr"
            in response.json()["notebook_url"]
        )
        mock_s3.put_object.assert_called_once_with(
            Body=request_data["notebook_json"],
            Bucket="test-bucket",
            Key=f"{request_obj.folder}/{request_obj.notebook_name}-{test_hash}.ipynb",
        )

    pass
