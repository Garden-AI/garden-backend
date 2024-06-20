import pytest


@pytest.mark.asyncio
@pytest.mark.container
async def test_mint_draft_doi(
    client,
    mock_auth_state,
    mock_settings,
    override_authenticated_dependency,
    override_get_settings_dependency,
    mocker,
):
    mock_request_body = {"data": {"type": "dois", "attributes": {}}}
    mock_response_body = {
        "data": {"type": "dois", "attributes": {"doi": "10.fake/doi"}}
    }
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = mock_response_body
    mock_post.return_value.raise_for_status.return_value = None

    response = await client.post("/doi", json=mock_request_body)

    assert response.status_code == 201
    assert response.json() == {"doi": "10.fake/doi"}


@pytest.mark.asyncio
@pytest.mark.container
async def test_update_datacite(
    client,
    mock_auth_state,
    mock_settings,
    override_authenticated_dependency,
    override_get_settings_dependency,
    mocker,
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
    mock_put = mocker.patch("requests.put")
    mock_put.return_value.json.return_value = mock_request_body
    mock_put.return_value.raise_for_status.return_value = None

    response = await client.put("/doi", json=mock_request_body)

    assert response.status_code == 200
    assert response.json() == mock_request_body
