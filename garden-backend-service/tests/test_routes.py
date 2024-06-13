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
from testcontainers.postgres import PostgresContainer

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
