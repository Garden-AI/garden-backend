import random
from copy import deepcopy

import pytest

from src.api.dependencies.auth import authenticated
from src.main import app
from tests.utils import post_entrypoints, post_garden


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
    # Store the DOI from the response for subsequent assertions
    created_doi = response_data["doi"]
    assert created_doi is not None
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

    response = await client.post("/gardens", json=create_garden_two_entrypoints_json)
    assert response.status_code == 200
    created_doi = response.json()["doi"]

    response = await client.get(f"/gardens/{created_doi}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == created_doi
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

    response = await client.post("/gardens", json=create_garden_two_entrypoints_json)
    assert response.status_code == 200
    created_doi = response.json()["doi"]

    response = await client.delete(f"/gardens/{created_doi}")
    assert response.status_code == 200
    assert response.json() == {
        "detail": f"Successfully deleted garden with DOI {created_doi}."
    }

    # Verify deletion is idempotent
    response = await client.delete(f"/gardens/{created_doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No garden found with DOI {created_doi}."}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_doi(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we are looking for
    response = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert response.status_code == 200
    created_doi = response.json()["doi"]

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    response = await client.post("/gardens", json=new_garden)
    assert response.status_code == 200

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"doi": [created_doi]},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["doi"] == created_doi


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_by_draft(
    client,
    mock_db_session,
    mock_garden_create_request_no_entrypoints_json,
    override_authenticated_dependency,
):
    # Post the garden we are looking for
    response = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert response.status_code == 200

    # Post another garden
    new_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    response = await client.post("/gardens", json=new_garden)
    assert response.status_code == 200
    doi = response.json()["doi"]
    # publish the other garden
    patch_response = await client.patch(f"/gardens/{doi}", json={"doi_is_draft": False})
    assert patch_response.status_code == 200

    # Search for the first garden
    response = await client.get(
        "/gardens",
        params={"draft": "true"},
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
    mock_auth_state_other_user,
):
    # Add a garden by another user
    app.dependency_overrides[authenticated] = lambda: mock_auth_state_other_user
    _ = await client.get("/greet")
    other_users_garden = deepcopy(mock_garden_create_request_no_entrypoints_json)
    other_users_garden["doi"] = "new/doi"
    await post_garden(client, other_users_garden)

    # Add garden by the user we are looking for
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
    _ = await client.get("/greet")
    await post_garden(client, mock_garden_create_request_no_entrypoints_json)

    # Search for the garden
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
        response = await client.post(
            "/gardens", json=mock_garden_create_request_no_entrypoints_json
        )
        assert response.status_code == 200
        created_doi = response.json()["doi"]
        doi_list.append(created_doi)

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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_garden_partial_update(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    # post a new garden
    post_response = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert post_response.status_code == 200

    # Update the garden
    doi = post_response.json()["doi"]
    updated_data = {"tags": ["Some", "New", "Tags"]}
    patch_response = await client.patch(f"/gardens/{doi}", json=updated_data)
    assert patch_response.status_code == 200
    data = patch_response.json()
    assert set(updated_data["tags"]) == set(data["tags"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_garden_archive(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
    mock_doi_utils,
):
    mock_garden_create_request_no_entrypoints_json["doi_is_draft"] = False
    # post a new registered garden
    post_response = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert post_response.status_code == 200

    assert post_response.json()["state"] == "DRAFT"
    doi = post_response.json()["doi"]
    # publish then archive it
    patch_response = await client.patch(f"/gardens/{doi}", json={"doi_is_draft": False})
    assert patch_response.status_code == 200
    assert patch_response.json()["state"] == "PUBLISHED"

    patch_response = await client.patch(f"/gardens/{doi}", json={"is_archived": True})
    assert patch_response.status_code == 200, patch_response.json()
    assert patch_response.json()["state"] == "ARCHIVED"

    # verify that archive request was sent to datacite
    mock_doi_utils["archive_doi"].assert_called_once()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_garden_archive_and_draft(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    # post a new garden
    post_response = await client.post(
        "/gardens", json=mock_garden_create_request_no_entrypoints_json
    )
    assert post_response.status_code == 200

    # Update the garden, should return an error code
    # Cannot archive a draft garden
    doi = post_response.json()["doi"]
    updated_data = {"is_archived": True}
    patch_response = await client.patch(f"/gardens/{doi}", json=updated_data)
    assert patch_response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_archived_garden_fails(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_archived_json,
):
    # post a new garden
    post_response = await client.post(
        "/gardens", json=mock_garden_create_request_archived_json
    )
    assert post_response.status_code == 200

    # Updating the garden should succeed since draft is default
    doi = post_response.json()["doi"]
    updated_data = {"title": "New Title"}
    patch_response = await client.patch(f"/gardens/{doi}", json=updated_data)
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "New Title"

    # publish then archive it
    patch_response = await client.patch(f"/gardens/{doi}", json={"doi_is_draft": False})
    assert patch_response.status_code == 200

    patch_response = await client.patch(f"/gardens/{doi}", json={"is_archived": True})
    assert patch_response.status_code == 200

    # now updates should fail
    patch_response = await client.patch(
        f"/gardens/{doi}", json={"title": "Newer Title"}
    )
    assert patch_response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unarchive_garden(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_archived_json,
):
    # post a new garden
    post_response = await client.post(
        "/gardens", json=mock_garden_create_request_archived_json
    )
    assert post_response.status_code == 200

    # Unarchive the garden
    # Should return a 200 status code
    doi = post_response.json()["doi"]
    updated_data = {"is_archived": False, "title": "Other Update"}
    patch_response = await client.patch(f"/gardens/{doi}", json=updated_data)
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Other Update"
    assert not patch_response.json()["is_archived"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_rejects_invalid_filters(
    client,
    override_get_settings_dependency,
):
    body = {
        "q": "some search query",
        "filters": [
            {
                "field_name": "some_invalid_field",
                "values": ["some value"],
            },
        ],
    }
    response = await client.post("/gardens/search", json=body)
    assert response.status_code == 400
    assert "Invalid filter" in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_returns_gardens(
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
    await post_garden(client, create_garden_two_entrypoints_json)

    body = {
        "q": "Owen",
    }
    response = await client.post("/gardens/search", json=body)
    assert response.status_code == 200
    search_result = response.json()

    assert len(search_result["garden_meta"]) == 1
    assert search_result["count"] == 1
    assert search_result["offset"] == 0
    assert search_result["facets"]["model_authors"] == {"Owen": 1}
    assert search_result["facets"]["year"] == {"2023": 1}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_applies_filters_correctly(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
    mock_auth_state,
):
    g1 = mock_garden_create_request_no_entrypoints_json

    g2 = deepcopy(mock_garden_create_request_no_entrypoints_json)
    g2["authors"] = ["Phillip J. Fry"]
    g2["doi"] = "12.345/fake-doi"

    g3 = deepcopy(mock_garden_create_request_no_entrypoints_json)
    g3["doi"] = "34.567/fake-doi"
    g3["tags"] = ["testing"]
    g3["description"] = "a garden for testing"

    await post_garden(client, g1)
    await post_garden(client, g2)
    await post_garden(client, g3)

    body = {
        "q": "Garden",
        "filters": [
            {"field_name": "authors", "values": ["Owen"]},
            {"field_name": "tags", "values": ["testing"]},
            {"field_name": "description", "values": ["testing"]},
            {"field_name": "owner", "values": [f"{mock_auth_state.name}"]},
        ],
    }
    response = await client.post("gardens/search", json=body)
    assert response.status_code == 200

    search_result = response.json()
    assert len(search_result["garden_meta"]) == 1
    assert search_result["garden_meta"][0]["authors"][0] == "Owen"
    assert search_result["facets"]["model_authors"] == {"Owen": 1}
    assert search_result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_returns_empty_list_when_no_matches(
    client,
    mock_db_session,
):
    body = {
        "q": "some query",
    }
    response = await client.post("/gardens/search", json=body)
    assert response.status_code == 200
    search_result = response.json()
    assert search_result["total"] == 0
    assert search_result["count"] == 0
    assert len(search_result["garden_meta"]) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_facet_counts_are_correct(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    g1 = mock_garden_create_request_no_entrypoints_json

    g2 = deepcopy(mock_garden_create_request_no_entrypoints_json)
    g2["doi"] = "12.345/fake-doi"

    g3 = deepcopy(mock_garden_create_request_no_entrypoints_json)
    g3["doi"] = "34.567/fake-doi"
    g3["tags"] = ["testing"]

    await post_garden(client, g1)
    await post_garden(client, g2)
    await post_garden(client, g3)

    q1 = {
        "q": "garden",
    }
    res1 = await client.post("gardens/search", json=q1)
    assert res1.status_code == 200
    search_res1 = res1.json()
    facets1 = search_res1["facets"]
    assert facets1["model_authors"]["Owen"] == 3
    assert facets1["tags"]["python"] == 2
    assert facets1["tags"]["testing"] == 1
    assert facets1["year"]["2023"] == 3

    q2 = {
        "q": "garden",
        "filters": [
            {"field_name": "tags", "values": ["testing"]},
        ],
    }
    res2 = await client.post("gardens/search", json=q2)
    assert res2.status_code == 200
    search_res2 = res2.json()
    facets2 = search_res2["facets"]
    assert facets2["model_authors"]["Owen"] == 1
    assert facets2["tags"]["testing"] == 1
    assert facets2["year"]["2023"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_offset_paginates_results(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    for i in range(20):
        garden_data = deepcopy(mock_garden_create_request_no_entrypoints_json)
        garden_data["doi"] = f"12.345/some-doi-{i}"
        await post_garden(client, garden_data)

    body = {"q": "garden"}

    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 200
    result = res.json()
    assert result["total"] == 20
    assert result["count"] == 10
    assert result["offset"] == 0

    body = {"q": "garden", "offset": 15}
    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 200
    result = res.json()
    assert result["total"] == 20
    assert result["count"] == 5
    assert result["offset"] == 15


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_sort_by_title(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    sorted_titles = ["A", "B", "C", "D", "E", "F"]

    random_titles = list(sorted_titles)
    # shuffle until we know the lists are different
    while random_titles == sorted_titles:
        random.shuffle(random_titles)

    for title in random_titles:
        garden_data = deepcopy(mock_garden_create_request_no_entrypoints_json)
        garden_data["title"] = title
        garden_data["doi"] = f"12.345/some-doi-{title}"
        await post_garden(client, garden_data)

    body = {"q": "gardens", "sort": {"field_name": "title", "order": "asc"}}
    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 200
    result = res.json()
    titles = [g["title"] for g in result["garden_meta"]]
    assert titles == sorted_titles

    body = {"q": "gardens", "sort": {"field_name": "title", "order": "desc"}}
    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 200
    result = res.json()
    titles = [g["title"] for g in result["garden_meta"]]
    assert titles == list(reversed(sorted_titles))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_rejects_invalid_sort_field(
    client,
    mock_db_session,
):
    body = {
        "q": "some query",
        "sort": {
            "field_name": "some invalid field",
            "order": "desc",
        },
    }
    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 400
    assert "Invalid sort field_name" in res.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_gardens_rejects_invalid_sort_order(
    client,
    mock_db_session,
):
    body = {
        "q": "some query",
        "sort": {
            "field_name": "authors",
            "order": "not a valid sort order",
        },
    }
    res = await client.post("/gardens/search", json=body)
    assert res.status_code == 400
    assert "Invalid sort order" in res.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_garden_rejects_non_citable_patches(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_garden_create_request_no_entrypoints_json,
):
    # create a new garden with 1 author and no contributors
    garden_data = deepcopy(mock_garden_create_request_no_entrypoints_json)
    garden_data["authors"] = ["Amy Wong"]
    del garden_data["contributors"]
    post_response = await client.post(
        "/gardens",
        json=garden_data,
    )
    assert post_response.status_code == 200
    assert post_response.json()["authors"] == ["Amy Wong"]
    assert post_response.json()["contributors"] == []
    doi = post_response.json()["doi"]

    # a patch removing the author should fail
    patch_response = await client.patch(f"/gardens/{doi}", json={"authors": []})
    assert patch_response.status_code == 409

    # add a contributor
    patch_response = await client.patch(
        f"/gardens/{doi}", json={"contributors": ["Wernstrom"]}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["contributors"] == ["Wernstrom"]

    # we should now be able to remove the author
    patch_response = await client.patch(f"/gardens/{doi}", json={"authors": []})
    assert patch_response.status_code == 200
    assert patch_response.json()["authors"] == []

    # removing the contributor should fail
    patch_response = await client.patch(f"/gardens/{doi}", json={"contributors": []})
    assert patch_response.status_code == 409

    # add another author
    patch_response = await client.patch(
        f"/gardens/{doi}", json={"authors": ["Amy Wong"]}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["authors"] == ["Amy Wong"]

    # we should now be able to remove the contributor
    patch_response = await client.patch(f"/gardens/{doi}", json={"contributors": []})
    assert patch_response.status_code == 200
    assert patch_response.json()["contributors"] == []
