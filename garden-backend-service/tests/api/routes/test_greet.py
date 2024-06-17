import pytest


@pytest.mark.asyncio
async def test_greet_authed_user(
    client,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = await client.get("/greet")
    assert response.status_code == 200
    assert response.json() == {
        "Welcome, Monsieur.Sartre@ens-paris.fr": "you're looking very... authentic today."
    }


@pytest.mark.asyncio
async def test_missing_auth_header(
    client,
    mock_missing_token,
    override_get_db_session_dependency,
):
    response = await client.get("/greet")
    assert response.status_code == 403
    assert response.json() == {"detail": "Authorization header missing"}
