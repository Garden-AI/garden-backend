import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_and_get_hpc_function(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_function_json,
    create_hpc_endpoint_json,
):
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()

    create_hpc_function_json["endpoint_ids"] = [endpoint["id"]]

    create_response = await client.post("/hpc/functions", json=create_hpc_function_json)
    assert create_response.status_code == 200
    created_data = create_response.json()
    assert created_data["function_name"] == create_hpc_function_json["function_name"]
    function_id = created_data["id"]

    get_response = await client.get(f"/hpc/functions/{function_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["id"] == function_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_hpc_function(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_function_json,
    create_hpc_endpoint_json,
):
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()

    create_hpc_function_json["endpoint_ids"] = [endpoint["id"]]

    create_response = await client.post("/hpc/functions", json=create_hpc_function_json)
    function_id = create_response.json()["id"]

    patch_response = await client.patch(
        f"/hpc/functions/{function_id}", json={"tags": ["updated"]}
    )
    assert patch_response.status_code == 200
    assert "updated" in patch_response.json()["tags"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_hpc_function(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_function_json,
    create_hpc_endpoint_json,
):
    """Test successful deletion of an HPC function."""
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()

    create_hpc_function_json["endpoint_ids"] = [endpoint["id"]]

    create_response = await client.post("/hpc/functions", json=create_hpc_function_json)
    function_id = create_response.json()["id"]

    # Deletion should succeed
    delete_response = await client.delete(f"/hpc/functions/{function_id}")
    assert delete_response.status_code == 200
    assert "Successfully deleted" in delete_response.json()["detail"]

    # Function should no longer exist
    get_response = await client.get(f"/hpc/functions/{function_id}")
    assert get_response.status_code == 404

    # Test deleting a non-existent function
    delete_response_404 = await client.delete("/hpc/functions/99999")
    assert delete_response_404.status_code == 404
