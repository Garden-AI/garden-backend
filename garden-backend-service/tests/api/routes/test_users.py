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
        "phone_number": "1234567890",
        "skills": ["Python", "FastAPI"],
        "domains": ["Web Development"],
        "affiliations": ["New Affiliation"],
    }

    response = await client.patch("/users", json=update_payload)
    assert response.status_code == 200

    updated_user_data = response.json()
    assert updated_user_data["username"] == "new_username"
    assert updated_user_data["name"] == "New Name"
    assert updated_user_data["email"] == "new.email@example.com"
    assert updated_user_data["phone_number"] == "1234567890"
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
