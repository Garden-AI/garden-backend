from copy import deepcopy

import pytest


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
async def test_search_gardens_by_doi(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we are looking for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"doi": [mock_garden_create_request_no_entrypoints_json["doi"]]},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert (
        response_data[0]["doi"] == mock_garden_create_request_no_entrypoints_json["doi"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_doi_is_draft(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we are looking for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    new_garden["doi_is_draft"] = False
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={
            "doi_is_draft": mock_garden_create_request_no_entrypoints_json[
                "doi_is_draft"
            ]
        },
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert (
        response_data[0]["doi_is_draft"]
        == mock_garden_create_request_no_entrypoints_json["doi_is_draft"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_owner_uuid(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
    mock_auth_state,
):
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)
    response = await client.get(
        "/gardens",
        params={"owner_uuid": mock_auth_state.identity_id},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["owner_identity_id"] == str(mock_auth_state.identity_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_authors(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we are looking for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    new_garden["authors"] = ["new authors"]
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"authors": mock_garden_create_request_no_entrypoints_json["authors"]},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert set(response_data[0]["authors"]) == set(
        mock_garden_create_request_no_entrypoints_json["authors"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_contributors(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we will search for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    new_garden["contributors"] = ["new contributors"]
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={
            "contributors": mock_garden_create_request_no_entrypoints_json[
                "contributors"
            ]
        },
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert set(response_data[0]["contributors"]) == set(
        mock_garden_create_request_no_entrypoints_json["contributors"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_tags(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we will search for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    new_garden["tags"] = ["new tags"]
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"tags": mock_garden_create_request_no_entrypoints_json["tags"]},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert set(response_data[0]["tags"]) == set(
        mock_garden_create_request_no_entrypoints_json["tags"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_year(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we will search for
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    new_garden["doi"] = "new/doi"
    new_garden["year"] = "1970"
    await post_garden(client, new_garden)

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"year": mock_garden_create_request_no_entrypoints_json["year"]},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert (
        response_data[0]["year"]
        == mock_garden_create_request_no_entrypoints_json["year"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_with_limit(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    for i in range(10):
        mock_garden_create_request_no_entrypoints_json["doi"] = f"fake/doi-{i}"
        await post_garden(client, mock_garden_create_request_no_entrypoints_json)
    response = await client.get("/gardens", params={"limit": 5})
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 5


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_multiple_gardens_by_doi(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    doi_list = []
    for i in range(5):
        mock_garden_create_request_no_entrypoints_json["doi"] = f"fake/doi-{i}"
        doi_list.append(mock_garden_create_request_no_entrypoints_json["doi"])
        await post_garden(client, mock_garden_create_request_no_entrypoints_json)
    response = await client.get("/gardens", params={"doi": doi_list})
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 5
    assert set([garden["doi"] for garden in response_data]) == set(doi_list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_multiple_gardens_by_year(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    mock_garden_create_request_no_entrypoints_json["year"] = "2023"
    for i in range(5):
        mock_garden_create_request_no_entrypoints_json["doi"] = f"fake/doi-{i}"
        await post_garden(client, mock_garden_create_request_no_entrypoints_json)
    response = await client.get("/gardens", params={"year": "2023"})
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 5
    assert all(garden["year"] == "2023" for garden in response_data)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_combined_filters(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    for i in range(3):
        mock_garden_create_request_no_entrypoints_json["doi"] = f"fake/doi-{i}"
        mock_garden_create_request_no_entrypoints_json["year"] = "2022"
        mock_garden_create_request_no_entrypoints_json["authors"] = ["Author A"]
        await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    response = await client.get(
        "/gardens", params={"year": "2022", "authors": ["Author A"]}
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 3
    assert all(garden["year"] == "2022" for garden in response_data)
    assert all("Author A" in garden["authors"] for garden in response_data)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_no_results(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/gardens", params={"doi": ["nonexistent_doi"]})
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_empty_database(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    response = await client.get("/gardens")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0
