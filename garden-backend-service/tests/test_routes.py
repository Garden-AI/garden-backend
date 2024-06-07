import hashlib
from pathlib import Path
import json
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

import requests  # noqa
from fastapi.testclient import TestClient
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies.auth import (
    AuthenticationState,
    authenticated,
    _get_auth_token,
)
from src.api.dependencies.database import get_db_session
from src.api.schemas.notebook import UploadNotebookRequest
from src.config import Settings, get_settings
from src.main import app
from src.models.base import Base
from src.models import *  # noqa

client = TestClient(app)


@pytest.fixture(scope="session")
def mock_entrypoint_create_request_json() -> dict:
    path = Path(__file__).parent / "fixtures" / "EntrypointCreateRequest.json"
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


@pytest.fixture
async def mock_db_session(mock_settings):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)
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


@pytest.mark.asyncio
async def test_greet_authed_user(
    override_authenticated_dependency, override_get_db_session_dependency
):
    response = client.get("/greet")
    assert response.status_code == 200
    assert response.json() == {
        "Welcome, Monsieur.Sartre@ens-paris.fr": "you're looking very... authentic today."
    }


def test_missing_auth_header(mock_missing_token, override_get_db_session_dependency):
    response = client.get("/greet")
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


def test_greet_world():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello there": "You must be World"}


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
        folder="Monsieur.Sartre@ens-paris.fr",  # not a commentary on nabokov, just needs to match the auth mock
    )
    request_obj = UploadNotebookRequest(**request_data)
    test_hash = hashlib.sha256(request_obj.json().encode()).hexdigest()

    with patch("boto3.client") as mock_boto_client:
        mock_s3 = mock_boto_client.return_value
        response = client.post("/notebook", json=request_data)

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

    return
