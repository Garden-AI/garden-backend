import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_greet_authed_user(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/greet")
    assert response.status_code == 200
    assert response.json() == {
        "Welcome, Monsieur.Sartre@ens-paris.fr": "you're looking very... authentic today."
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_auth_header(
    client,
    mock_db_session,
    mock_missing_token,
):
    response = await client.get("/greet")
    assert response.status_code == 403
    assert response.json() == {"detail": "Authorization header missing"}
