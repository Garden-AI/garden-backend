import pytest


@pytest.mark.asyncio
async def test_greet_world(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello there": "You must be World"}
