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
from src.auth.globus_groups import add_user_to_group
from src.config import Settings, get_settings
from src.main import app
from src.models.base import Base

# from src.models import *  # noqa

client = TestClient(app)


@pytest.fixture(scope="session")
def create_entrypoint_with_related_metadata_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-with-metadata.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture(scope="session")
def create_shared_entrypoint_json() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "EntrypointCreateRequest-shared-entrypoint.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture(scope="session")
def create_garden_two_entrypoints_json(
    create_entrypoint_with_related_metadata_json, create_shared_entrypoint_json
) -> dict:
    """Request payload to create a garden referencing two other entrypoints by DOI.
    Note: Trying to create the garden before these entrypoints exist in the DB will cause an error.
    See:  create_entrypoint_with_related_metadata_json, create_shared_entrypoint_json
    """
    path = (
        Path(__file__).parent / "fixtures" / "GardenCreateRequest-two-entrypoints.json"
    )
    with open(path, "r") as f_in:
        return json.load(f_in)


@pytest.fixture(scope="session")
def create_garden_shares_entrypoint_json(
    create_entrypoint_with_related_metadata_json,
    create_shared_entrypoint_json,
    create_garden_two_entrypoints_json,
) -> list[dict]:
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
    mock_settings.GARDEN_USERS_GROUP_ID = "GARDEN_GROUP_UUID"
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


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_greet_authed_user(
    override_authenticated_dependency, override_get_db_session_dependency
):
    response = client.get("/greet")
    assert response.status_code == 200
    assert response.json() == {
        "Welcome, Monsieur.Sartre@ens-paris.fr": "you're looking very... authentic today."
    }


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
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


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_add_entrypoint(
    create_entrypoint_with_related_metadata_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = client.post(
        "/entrypoint", json=create_entrypoint_with_related_metadata_json
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_entrypoint_with_related_metadata_json["doi"]
    assert (
        response_data["title"] == create_entrypoint_with_related_metadata_json["title"]
    )
    assert (
        response_data["description"]
        == create_entrypoint_with_related_metadata_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_add_entrypoint_duplicate_doi(
    create_entrypoint_with_related_metadata_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    # First request to add entrypoint
    response = client.post(
        "/entrypoint", json=create_entrypoint_with_related_metadata_json
    )
    assert response.status_code == 200

    # Second request with the same data should fail due to duplicate DOI
    response = client.post(
        "/entrypoint", json=create_entrypoint_with_related_metadata_json
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Entrypoint with this DOI already exists"}


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_get_entrypoint_by_doi(
    create_entrypoint_with_related_metadata_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    # add the entrypoint
    response = client.post(
        "/entrypoint", json=create_entrypoint_with_related_metadata_json
    )
    assert response.status_code == 200

    # get by DOI
    doi = create_entrypoint_with_related_metadata_json["doi"]
    response = client.get(f"/entrypoint/{doi}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_entrypoint_with_related_metadata_json["doi"]
    assert (
        response_data["title"] == create_entrypoint_with_related_metadata_json["title"]
    )
    assert (
        response_data["description"]
        == create_entrypoint_with_related_metadata_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_get_entrypoint_by_doi_not_found(
    mock_db_session, override_get_db_session_dependency
):
    response = client.get("/entrypoint/10.fake/doi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Entrypoint not found with DOI 10.fake/doi"}


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_delete_entrypoint(
    create_entrypoint_with_related_metadata_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    # add then delete
    response = client.post(
        "/entrypoint", json=create_entrypoint_with_related_metadata_json
    )
    assert response.status_code == 200

    doi = create_entrypoint_with_related_metadata_json["doi"]
    response = client.delete(f"/entrypoint/{doi}")
    assert response.status_code == 200
    assert response.json() == {
        "detail": f"Successfully deleted entrypoint with DOI {doi}."
    }
    # delete is idempotent
    response = client.delete("/entrypoint/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": "No entrypoint found with DOI {doi}."}


@pytest.mark.asyncio
async def test_add_user_to_group(
    mocker,
    mock_auth_state,
    mock_settings,
):
    module = "src.auth.globus_groups"

    mock_groups_manager = MagicMock()
    mocker.patch(
        module + "._create_service_groups_manager",
        return_value=mock_groups_manager,
    )

    add_user_to_group(mock_auth_state, mock_settings)

    # Verify the user was added to the group
    mock_groups_manager.add_member.assert_called_once_with(
        mock_settings.GARDEN_USERS_GROUP_ID,
        mock_auth_state.identity_id,
    )


# GPT-generated "stub" tests for /garden routes -- likely to be broken even
# after get_db_session is fixed, if the test db state doesn't have the entrypoints
# referred to by the fixture data present.
@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_add_garden(
    create_garden_two_entrypoints_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = await client.post("/garden", json=create_garden_two_entrypoints_json)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_add_garden_with_missing_entrypoint(
    create_garden_two_entrypoints_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    create_garden_two_entrypoints_json["entrypoint_ids"].append("10.missing/doi")
    response = await client.post("/garden", json=create_garden_two_entrypoints_json)
    assert response.status_code == 404
    assert (
        "Failed to add garden. Could not find entrypoint(s) with DOIs"
        in response.json()["detail"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_get_garden_by_doi(
    create_garden_two_entrypoints_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    await client.post("/garden", json=create_garden_two_entrypoints_json)
    response = await client.get(f"/garden/{create_garden_two_entrypoints_json['doi']}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_get_garden_by_doi_not_found(
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = await client.get("/garden/10.missing/doi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Garden not found with DOI 10.missing/doi"}


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
async def test_delete_garden(
    create_garden_two_entrypoints_json,
    mock_db_session,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    await client.post("/garden", json=create_garden_two_entrypoints_json)
    doi = create_garden_two_entrypoints_json["doi"]
    response = await client.delete(f"/garden/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"Successfully deleted garden with DOI {doi}."}

    # Verify deletion is idempotent
    response = await client.delete(f"/garden/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No garden found with DOI {doi}."}
