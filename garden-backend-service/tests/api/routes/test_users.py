import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_info(
    client: AsyncClient, mock_db_session, override_authenticated_dependency
):
    response = await client.get("/users")
    assert response.status_code == 200

    user_data = response.json()
    assert "username" in user_data
    assert "email" in user_data
    assert "identity_id" in user_data
    assert "name" in user_data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_user_info(
    client: AsyncClient, mock_db_session, override_authenticated_dependency
):
    update_payload = {
        "username": "new_username",
        "name": "New Name",
        "email": "new.email@example.com",
        "phone_number": "+1-234-567-8900",
        "skills": ["Python", "FastAPI"],
        "domains": ["Web Development"],
        "affiliations": ["New Affiliation"],
    }

    response = await client.patch("/users", json=update_payload)
    if response.status_code != 200:
        print(response.json())

    assert response.status_code == 200

    updated_user_data = response.json()
    assert updated_user_data["username"] == "new_username"
    assert updated_user_data["name"] == "New Name"
    assert updated_user_data["email"] == "new.email@example.com"
    assert updated_user_data["phone_number"] == "tel:+1-234-567-8900"
    assert updated_user_data["skills"] == ["Python", "FastAPI"]
    assert updated_user_data["domains"] == ["Web Development"]
    assert updated_user_data["affiliations"] == ["New Affiliation"]

    response = await client.get("/users")
    user_data = response.json()
    assert user_data == updated_user_data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_partial_user_info(
    client: AsyncClient, mock_db_session, override_authenticated_dependency
):
    response = await client.get("/users")
    pre_update_user_data = response.json()

    update_payload = {
        "username": "partial_username",
    }

    response = await client.patch("/users", json=update_payload)
    assert response.status_code == 200

    updated_user_data = response.json()
    assert updated_user_data["username"] == "partial_username"
    assert updated_user_data != pre_update_user_data

    response = await client.get("/users")
    post_update_user_data = response.json()
    assert updated_user_data == post_update_user_data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_info_unauthenticated(
    client: AsyncClient, mock_missing_token, mock_db_session
):
    response = await client.get("/users")
    assert response.status_code == 403
    assert response.json()["detail"] == "Authorization header missing"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_user_info_invalid_payload(
    client: AsyncClient, mock_db_session, override_authenticated_dependency
):
    update_payload = {
        "username": 12345,  # Invalid type
        "email": "invalid-email-format",  # Invalid email format
    }

    response = await client.patch("/users", json=update_payload)
    assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unauthorized_access(
    client: AsyncClient, mock_missing_token, mock_db_session
):
    response = await client.get("/users")
    assert response.status_code == 403
    assert response.json()["detail"] == "Authorization header missing"

    update_payload = {
        "username": "unauthorized_user",
    }
    response = await client.patch("/users", json=update_payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Authorization header missing"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_garden(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_auth_state,
    mock_garden_create_request_no_entrypoints_json,
):
    # Post the garden we will save
    doi = mock_garden_create_request_no_entrypoints_json["doi"]
    res = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert res.status_code == 200

    # Post some other gardens
    for i in range(5):
        mock_garden_create_request_no_entrypoints_json["doi"] = f"fake/doi-{i}"
        res = await client.post(
            "/gardens", json=mock_garden_create_request_no_entrypoints_json
        )
        assert res.status_code == 200

    # Save the garden, we should get the updated list of saved gardens back
    res = await client.put(f"/users/{mock_auth_state.identity_id}/saved/gardens/{doi}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert doi == data[0]["doi"]

    # Saving the garden again should be idempotent
    res = await client.put(f"/users/{mock_auth_state.identity_id}/saved/gardens/{doi}")
    assert res.status_code == 200

    # Get the users saved gardens, should only have 1
    res = await client.get(f"/users/{mock_auth_state.identity_id}/saved/gardens")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert doi == data[0]["doi"]

    # Remove the saved garden
    res = await client.delete(
        f"/users/{mock_auth_state.identity_id}/saved/gardens/{doi}"
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 0

    # Removing the same saved garden again should be idempotent
    res = await client.delete(
        f"/users/{mock_auth_state.identity_id}/saved/gardens/{doi}"
    )
    assert res.status_code == 200

    # Get the users saved gardens again, make sure the garden is not present
    res = await client.get(f"/users/{mock_auth_state.identity_id}/saved/gardens")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_garden_no_auth(
    client,
    mock_missing_token,
    mock_db_session,
):
    response = await client.put("/users/some_UUID/saved/gardens/somedoi")
    assert response.status_code == 403

    response = await client.delete("users/some_UUID/saved/gardens/somedoi")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_garden_unauthorized(
    client,
    mock_db_session,
    mock_auth_state,
    mock_auth_state_other_user,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post a garden
    doi = mock_garden_create_request_no_entrypoints_json["doi"]
    res = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert res.status_code == 200

    # Try to save it to another users list of saved gardens
    result = await client.put(
        f"/users/{mock_auth_state_other_user.identity_id}/saved/gardens/{doi}"
    )
    assert result.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_saved_garden_unauthorized(
    client,
    mock_db_session,
    mock_auth_state,
    mock_auth_state_other_user,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post a garden
    doi = mock_garden_create_request_no_entrypoints_json["doi"]
    res = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert res.status_code == 200

    # Try and delete another users list of saved gardens
    result = await client.delete(
        f"/users/{mock_auth_state_other_user.identity_id}/saved/gardens/{doi}"
    )
    assert result.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_garden_nonexistent_garden(
    client,
    mock_db_session,
    mock_auth_state,
    override_authenticated_dependency,
):
    # Try and save a garden that doesn't exist
    result = await client.put(
        f"/users/{mock_auth_state.identity_id}/saved/gardens/somedoi"
    )
    assert result.status_code == 404

    # Try and remove a saved garden that doesn't exist
    result = await client.delete(
        f"/users/{mock_auth_state.identity_id}/saved/gardens/somedoi"
    )
    assert result.status_code == 404
