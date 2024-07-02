from copy import deepcopy

import pytest


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
