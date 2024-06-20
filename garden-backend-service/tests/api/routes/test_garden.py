import pytest


# GPT-generated "stub" tests for /garden routes -- likely to be broken even
# after get_db_session is fixed, if the test db state doesn't have the entrypoints
# referred to by the fixture data present.
@pytest.mark.skip
@pytest.mark.asyncio
@pytest.mark.container
async def test_add_garden(
    client,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = await client.post("/garden", json=create_garden_two_entrypoints_json)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
@pytest.mark.container
async def test_add_garden_with_missing_entrypoint(
    client,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    create_garden_two_entrypoints_json["entrypoint_ids"].append("10.missing/doi")
    response = await client.post("/garden", json=create_garden_two_entrypoints_json)
    assert response.status_code == 404
    assert (
        "Failed to add garden. Could not find entrypoint(s) with DOIs"
        in response.json()["detail"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
@pytest.mark.container
async def test_get_garden_by_doi(
    client,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    await client.post("/garden", json=create_garden_two_entrypoints_json)
    response = await client.get(f"/garden/{create_garden_two_entrypoints_json['doi']}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["doi"] == create_garden_two_entrypoints_json["doi"]
    assert response_data["title"] == create_garden_two_entrypoints_json["title"]
    assert (
        response_data["description"]
        == create_garden_two_entrypoints_json["description"]
    )


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
@pytest.mark.container
async def test_get_garden_by_doi_not_found(
    client,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    response = await client.get("/garden/10.missing/doi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Garden not found with DOI 10.missing/doi"}


@pytest.mark.skip(
    "skip until get_db_session is fixed (https://github.com/Garden-AI/garden-backend/issues/94)"
)
@pytest.mark.asyncio
@pytest.mark.container
async def test_delete_garden(
    client,
    create_garden_two_entrypoints_json,
    override_authenticated_dependency,
    override_get_db_session_dependency,
):
    await client.post("/garden", json=create_garden_two_entrypoints_json)
    doi = create_garden_two_entrypoints_json["doi"]
    response = await client.delete(f"/garden/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"Successfully deleted garden with DOI {doi}."}

    # Verify deletion is idempotent
    response = await client.delete(f"/garden/{doi}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No garden found with DOI {doi}."}
