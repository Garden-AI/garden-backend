import copy
from unittest.mock import patch

import pytest

from src.api.dependencies.auth import authenticated
from src.main import app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_entrypoint(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == mock_entrypoint_create_request_json["doi"]
    assert response_data["title"] == mock_entrypoint_create_request_json["title"]
    assert (
        response_data["description"]
        == mock_entrypoint_create_request_json["description"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_entrypoint_duplicate_doi(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # First request to add entrypoint
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200

    # Second request with the same data should fail due to duplicate DOI
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Entrypoint with this DOI already exists"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoint_by_doi(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # add the entrypoint
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200

    # get by DOI
    doi = mock_entrypoint_create_request_json["doi"]
    response = await client.get(
        f"/entrypoints/{doi}",
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == mock_entrypoint_create_request_json["doi"]
    assert response_data["title"] == mock_entrypoint_create_request_json["title"]
    assert (
        response_data["description"]
        == mock_entrypoint_create_request_json["description"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoint_by_doi_not_found(
    client,
    mock_db_session,
):
    response = await client.get("/entrypoints/10.fake/doi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Entrypoint not found with DOI 10.fake/doi"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_entrypoint(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # add then delete
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200

    doi = mock_entrypoint_create_request_json["doi"]
    response = await client.delete(f"/entrypoints/{doi}")
    assert response.status_code == 200
    assert response.json() == {
        "detail": f"Successfully deleted entrypoint with DOI {doi}."
    }
    response = await client.delete("/entrypoints/10.fake/doi")
    assert response.status_code == 200
    assert response.json() == {"detail": "No entrypoint found with DOI 10.fake/doi."}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_entrypoint(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    doi = mock_entrypoint_create_request_json["doi"]
    # First, create the entrypoint with a PUT instead of POST
    response = await client.put(
        f"/entrypoints/{doi}", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200

    # put some updated data to the same place
    updated_data = copy.deepcopy(mock_entrypoint_create_request_json)
    updated_data["title"] = "Updated Title"
    # include a nested metadata field
    updated_data["datasets"][0]["title"] = "Updated Dataset Title"
    response = await client.put(f"/entrypoints/{doi}", json=updated_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == updated_data["doi"]
    assert response_data["title"] == updated_data["title"]
    assert response_data["datasets"][0]["title"] == "Updated Dataset Title"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_dois(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # Add an entrypoint
    response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert response.status_code == 200

    doi = mock_entrypoint_create_request_json["doi"]
    response = await client.get(f"/entrypoints?doi={doi}")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["doi"] == doi


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_tags(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # Add an entrypoint with specific tags
    tags = ["tag1", "tag2"]
    entrypoint_data_with_tags = copy.deepcopy(mock_entrypoint_create_request_json)
    entrypoint_data_with_tags["tags"] = tags
    response = await client.post("/entrypoints", json=entrypoint_data_with_tags)
    assert response.status_code == 200

    response = await client.get("/entrypoints?tags=tag1")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert "tag1" in response_data[0]["tags"]

    response = await client.get("/entrypoints?tags=tag3")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_authors(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # Add an entrypoint with specific authors
    authors = ["author1", "author2"]
    entrypoint_data_with_authors = copy.deepcopy(mock_entrypoint_create_request_json)
    entrypoint_data_with_authors["authors"] = authors
    response = await client.post("/entrypoints", json=entrypoint_data_with_authors)
    assert response.status_code == 200

    response = await client.get("/entrypoints?authors=author1")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert "author1" in response_data[0]["authors"]

    response = await client.get("/entrypoints?authors=author3")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_owner(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    mock_auth_state,
    mock_auth_state_other_user,
):
    # ensure both users in DB
    app.dependency_overrides[authenticated] = lambda: mock_auth_state_other_user
    _ = await client.get("/greet")
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
    _ = await client.get("/greet")

    # Add entrypoint with other user's uuid
    owner_id = str(mock_auth_state_other_user.identity_id)
    entrypoint_data_with_owner = copy.deepcopy(mock_entrypoint_create_request_json)
    # ... a gift for the madame
    entrypoint_data_with_owner["owner_identity_id"] = owner_id
    response = await client.post("/entrypoints", json=entrypoint_data_with_owner)
    assert response.status_code == 200

    response = await client.get(f"/entrypoints?owner_uuid={owner_id}")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["owner_identity_id"] == owner_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_draft(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # Add an entrypoint with draft status
    entrypoint_data_draft = copy.deepcopy(mock_entrypoint_create_request_json)
    entrypoint_data_draft["doi_is_draft"] = True
    response = await client.post("/entrypoints", json=entrypoint_data_draft)
    assert response.status_code == 200

    response = await client.get("/entrypoints?draft=true")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["doi_is_draft"] is True

    response = await client.get("/entrypoints?draft=false")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_entrypoints_with_year(
    client,
    mock_db_session,
    mock_entrypoint_create_request_json,
    override_authenticated_dependency,
):
    # Add an entrypoint with a specific year
    year = "2023"
    entrypoint_data_with_year = copy.deepcopy(mock_entrypoint_create_request_json)
    entrypoint_data_with_year["year"] = year
    response = await client.post("/entrypoints", json=entrypoint_data_with_year)
    assert response.status_code == 200

    response = await client.get(f"/entrypoints?year={year}")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["year"] == year

    response = await client.get("/entrypoints?year=2024")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_entrypoint_partial_update(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_entrypoint_create_request_json,
):
    # post a new entrypoint
    post_response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert post_response.status_code == 200

    # Update the entrypoint
    doi = mock_entrypoint_create_request_json["doi"]
    updated_data = {"tags": ["Some", "New", "Tags"]}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 200
    data = patch_response.json()
    for key, value in data.items():
        if key == "tags":
            assert value == updated_data["tags"]
        elif mock_entrypoint_create_request_json.get(key) is not None:
            assert value == mock_entrypoint_create_request_json.get(key)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_entrypoint_archive(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_entrypoint_create_request_json,
):
    mock_entrypoint_create_request_json["doi_is_draft"] = False
    with patch("src.api.routes.entrypoints.archive_on_datacite") as mock_archive:
        # post a new registered entrypoint
        post_response = await client.post(
            "/entrypoints", json=mock_entrypoint_create_request_json
        )
        assert post_response.status_code == 200

        # Update the entrypoint and verify the response
        doi = mock_entrypoint_create_request_json["doi"]
        updated_data = {"is_archived": True}
        patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
        assert patch_response.status_code == 200
        mock_archive.assert_called_once()
        data = patch_response.json()
        assert data["doi"] == doi
        assert data["is_archived"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_entrypoint_archive_and_draft(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_entrypoint_create_request_json,
):
    # post a new entrypoint
    post_response = await client.post(
        "/entrypoints", json=mock_entrypoint_create_request_json
    )
    assert post_response.status_code == 200

    # Update the entrypoint, should return an error code
    # Cannot archive a draft entrypoint
    doi = mock_entrypoint_create_request_json["doi"]
    updated_data = {"is_archived": True}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_archived_entrypoint_fails(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_entrypoint_archived_json,
):
    # post a new entrypoint
    post_response = await client.post(
        "/entrypoints", json=create_entrypoint_archived_json
    )
    assert post_response.status_code == 200

    # Update the entrypoint, should return an error code
    # Cannot update an archived entrypoint
    doi = create_entrypoint_archived_json["doi"]
    updated_data = {"title": "New Title"}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unarchive_entrypoint(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_entrypoint_archived_json,
):
    # post a new entrypoint
    post_response = await client.post(
        "/entrypoints", json=create_entrypoint_archived_json
    )
    assert post_response.status_code == 200

    # Unarchive the entrypoint
    # Should return a 200 status code
    doi = create_entrypoint_archived_json["doi"]
    updated_data = {"is_archived": False, "title": "Other Update"}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 200
    assert not patch_response.json()["is_archived"]
    assert patch_response.json()["title"] == "Other Update"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_disallow_editing_published_entrypoint_fields(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_published_entrypoint_json,
):
    # post a new entrypoint
    post_response = await client.post(
        "/entrypoints", json=create_published_entrypoint_json
    )
    assert post_response.status_code == 200
    # Ensure the entrypoint is marked as published
    assert post_response.json()["doi_is_draft"] is False
    assert post_response.json()["is_archived"] is False

    # Update various disallowed fields of the entrypoint
    # Should return a 400 status code
    doi = create_published_entrypoint_json["doi"]
    updated_data = {"short_name": "new_short_name"}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 400

    updated_data = {"func_uuid": "12345678-1234-5678-1234-567812345678"}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 400

    updated_data = {"container_uuid": "12345678-1234-5678-1234-567812345678"}
    patch_response = await client.patch(f"/entrypoints/{doi}", json=updated_data)
    assert patch_response.status_code == 400
