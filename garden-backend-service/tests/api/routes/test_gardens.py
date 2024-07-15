from copy import deepcopy

import pytest
from httpx import AsyncClient


async def post_garden(client, garden_data):
    """POST garden data to populate mock DB session.

    NB: this is not a fixture!
    """
    response = await client.post("/gardens", json=garden_data)
    assert response.status_code == 200
    return response.json()


async def post_entrypoints(client, *payloads):
    """POST entrypoint fixture data to populate mock DB session.

    NB: this is not a fixture!
    """
    for entrypoint_json in payloads:
        response = await client.post("/entrypoints", json=entrypoint_json)
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_garden(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_entrypoint_with_related_metadata_json,
    create_shared_entrypoint_json,
    create_garden_two_entrypoints_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )
    response = await client.post("/gardens", json=create_garden_two_entrypoints_json)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_garden_with_missing_entrypoint(
    client,
    mock_db_session,
    create_entrypoint_with_related_metadata_json,
    create_shared_entrypoint_json,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )
    payload = deepcopy(create_garden_two_entrypoints_json)
    payload["entrypoint_ids"].append("10.missing/doi")
    response = await client.post("/gardens", json=payload)
    assert response.status_code == 404
    assert "Could not find entrypoint(s) with DOIs" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_garden_by_doi(
    client,
    mock_db_session,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    await client.post("/gardens", json=create_garden_two_entrypoints_json)

    response = await client.get(f"/gardens/{create_garden_two_entrypoints_json['doi']}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_garden_by_doi_not_found(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/gardens/10.missing/doi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Garden not found with DOI 10.missing/doi"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_garden(
    client,
    mock_db_session,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    await client.post("/gardens", json=create_garden_two_entrypoints_json)
    doi = create_garden_two_entrypoints_json["doi"]
    response = await client.delete(f"/gardens/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"Successfully deleted garden with DOI {doi}."}

    # Verify deletion is idempotent
    response = await client.delete(f"/gardens/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No garden found with DOI {doi}."}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_put_updated_garden(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_entrypoint_with_related_metadata_json,
    create_shared_entrypoint_json,
    create_garden_two_entrypoints_json,
):
    garden_doi = create_garden_two_entrypoints_json["doi"]
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    response = await client.put(
        f"/gardens/{garden_doi}", json=create_garden_two_entrypoints_json
    )
    assert response.status_code == 200
    assert len(response.json()["entrypoints"]) == 2

    updated_payload = deepcopy(create_garden_two_entrypoints_json)
    updated_payload["title"] = "Updated Title"
    # only one of the DOIs this time
    updated_payload["entrypoint_ids"] = [create_shared_entrypoint_json["doi"]]

    response = await client.put(f"/gardens/{garden_doi}", json=updated_payload)
    assert response.status_code == 200
    assert len(response.json()["entrypoints"]) == 1
    assert response.json()["title"] == "Updated Title"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_no_filters(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )
    await post_garden(client, create_garden_two_entrypoints_json)

    response = await client.get("/gardens")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == create_garden_two_entrypoints_json["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_filter_by_user_id(
    client: AsyncClient,
    mock_db_session,
    mock_auth_state,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    garden1 = deepcopy(create_garden_two_entrypoints_json)
    garden1["doi"] = "10.1234/doi1"

    garden2 = deepcopy(create_garden_two_entrypoints_json)
    garden2["doi"] = "10.1234/doi2"

    await post_garden(client, garden1)
    await post_garden(client, garden2)

    response = await client.get(f"/gardens?uuid={mock_auth_state.identity_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == garden1["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_filter_by_authors(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    garden1 = deepcopy(create_garden_two_entrypoints_json)
    garden1["authors"] = ["Author 1", "Author 2"]
    garden1["doi"] = "10.1234/doi1"

    garden2 = deepcopy(create_garden_two_entrypoints_json)
    garden2["authors"] = ["Author 3"]
    garden2["doi"] = "10.1234/doi2"

    await post_garden(client, garden1)
    await post_garden(client, garden2)

    response = await client.get("/gardens?authors=Author 1,Author 2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == garden1["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_filter_by_tags(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    garden1 = deepcopy(create_garden_two_entrypoints_json)
    garden1["tags"] = ["Tag 1", "Tag 2"]
    garden1["doi"] = "10.1234/doi1"

    garden2 = deepcopy(create_garden_two_entrypoints_json)
    garden2["tags"] = ["Tag 3"]
    garden2["doi"] = "10.1234/doi2"

    await post_garden(client, garden1)
    await post_garden(client, garden2)

    response = await client.get("/gardens?tags=Tag 1,Tag 2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == garden1["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_filter_by_year(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    garden1 = deepcopy(create_garden_two_entrypoints_json)
    garden1["year"] = "2023"
    garden1["doi"] = "10.1234/doi1"

    garden2 = deepcopy(create_garden_two_entrypoints_json)
    garden2["year"] = "2022"
    garden2["doi"] = "10.1234/doi2"

    await post_garden(client, garden1)
    await post_garden(client, garden2)

    response = await client.get("/gardens?year=2023")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == garden1["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_limit(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )

    gardens = [deepcopy(create_garden_two_entrypoints_json) for i in range(5)]
    for i, garden in enumerate(gardens):
        garden["title"] = f"Garden {i}"
        garden["doi"] = f"10.1234/doi{i}"
        await post_garden(client, garden)

    response = await client.get("/gardens?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_no_results(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/gardens?user_id=9999")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_users_gardens(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
    create_garden_two_entrypoints_json,
    create_shared_entrypoint_json,
    create_entrypoint_with_related_metadata_json,
):
    await post_entrypoints(
        client,
        create_shared_entrypoint_json,
        create_entrypoint_with_related_metadata_json,
    )
    await post_garden(client, create_garden_two_entrypoints_json)

    response = await client.get("/gardens")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == create_garden_two_entrypoints_json["title"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_users_gardens_no_results(
    client: AsyncClient,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/gardens")
    assert response.status_code == 404
