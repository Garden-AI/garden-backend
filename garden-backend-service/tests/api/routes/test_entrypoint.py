import pytest


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
