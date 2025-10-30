import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_hpc_endpoint(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_is_super_user_dependency,
    create_hpc_endpoint_json,
):
    """Test updating an HPC endpoint's properties."""
    # Create an endpoint
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()
    endpoint_id = endpoint["id"]

    # Patch with a new name
    patch_data = {"name": "Updated Name"}
    patch_response = await client.patch(
        f"/hpc/endpoints/{endpoint_id}", json=patch_data
    )
    assert patch_response.status_code == 200
    updated_endpoint = patch_response.json()

    # Verify the update
    assert updated_endpoint["name"] == patch_data["name"]
    assert updated_endpoint["gcmu_id"] == create_hpc_endpoint_json["gcmu_id"]

    # Test patching a non-existent endpoint
    patch_response_404 = await client.patch(
        "/hpc/endpoints/99999", json={"name": "New Name"}
    )
    assert patch_response_404.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_hpc_endpoint(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_is_super_user_dependency,
    create_hpc_endpoint_json,
    create_hpc_function_json,
):
    """Test deletion of an HPC endpoint and its constraints."""
    # Create an endpoint
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()
    endpoint_id = endpoint["id"]

    # Create a function that uses this endpoint
    create_hpc_function_json["endpoint_ids"] = [endpoint_id]
    function_response = await client.post(
        "/hpc/functions", json=create_hpc_function_json
    )
    assert function_response.status_code == 200
    function_id = function_response.json()["id"]

    # Attempt to delete the endpoint while it's in use
    delete_response_400 = await client.delete(f"/hpc/endpoints/{endpoint_id}")
    assert delete_response_400.status_code == 400
    assert "Cannot delete endpoint used by" in delete_response_400.json()["detail"]

    # Delete the function, then retry deleting the endpoint
    await client.delete(f"/hpc/functions/{function_id}")

    # Deletion should now succeed
    delete_response_200 = await client.delete(f"/hpc/endpoints/{endpoint_id}")
    assert delete_response_200.status_code == 200
    assert "Successfully deleted" in delete_response_200.json()["detail"]

    # Verify the endpoint is gone
    get_response = await client.get(f"/hpc/endpoints/{endpoint_id}")
    assert get_response.status_code == 404

    # Test deleting a non-existent endpoint
    delete_response_404 = await client.delete("/hpc/endpoints/99999")
    assert delete_response_404.status_code == 404
