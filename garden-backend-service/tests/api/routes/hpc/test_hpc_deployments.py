import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_hpc_deployment(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_is_super_user_dependency,
    create_hpc_endpoint_json,
    create_hpc_deployment_json,
):
    """Test updating an HPC deployment's properties."""
    # Create two endpoints
    endpoint1_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint1_response.status_code == 200
    endpoint1 = endpoint1_response.json()

    create_hpc_endpoint_json["name"] = "Endpoint 2"
    create_hpc_endpoint_json["gcmu_id"] = "uuid-2"
    endpoint2_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint2_response.status_code == 200
    endpoint2 = endpoint2_response.json()

    # Create deployment with the first endpoint
    create_hpc_deployment_json["endpoint_ids"] = [endpoint1["id"]]
    deployment_response = await client.post(
        "/hpc/deployments", json=create_hpc_deployment_json
    )
    assert deployment_response.status_code == 200
    deployment = deployment_response.json()
    deployment_id = deployment["id"]

    # Patch with new values
    patch_data = {
        "conda_env_path": "/new/path/to/env",
        "endpoint_ids": [endpoint2["id"]],
        "user_endpoint_config": {"key": "value"},
    }
    patch_response = await client.patch(
        f"/hpc/deployments/{deployment_id}", json=patch_data
    )
    assert patch_response.status_code == 200
    updated_deployment = patch_response.json()

    # Verify updates
    assert updated_deployment["conda_env_path"] == patch_data["conda_env_path"]
    assert (
        updated_deployment["user_endpoint_config"] == patch_data["user_endpoint_config"]
    )
    assert endpoint2["id"] in updated_deployment["endpoint_ids"]
    assert endpoint1["id"] not in updated_deployment["endpoint_ids"]

    # Test patching a non-existent deployment
    patch_response_404 = await client.patch(
        "/hpc/deployments/99999", json={"conda_env_path": "/new/path"}
    )
    assert patch_response_404.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_hpc_deployment(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_is_super_user_dependency,
    create_hpc_deployment_json,
    create_hpc_function_json,
    create_hpc_endpoint_json,
):
    """Test deletion of an HPC deployment and its constraints."""
    # Create endpoint and deployment
    endpoint_response = await client.post(
        "/hpc/endpoints", json=create_hpc_endpoint_json
    )
    assert endpoint_response.status_code == 200
    endpoint = endpoint_response.json()

    create_hpc_deployment_json["endpoint_ids"] = [endpoint["id"]]
    deployment_response = await client.post(
        "/hpc/deployments", json=create_hpc_deployment_json
    )
    assert deployment_response.status_code == 200
    deployment = deployment_response.json()
    deployment_id = deployment["id"]

    # Create a function that uses this deployment
    create_hpc_function_json["deployment_ids"] = [deployment_id]
    function_response = await client.post(
        "/hpc/functions", json=create_hpc_function_json
    )
    assert function_response.status_code == 200

    # Attempt to delete the deployment while it's in use
    delete_response_400 = await client.delete(f"/hpc/deployments/{deployment_id}")
    assert delete_response_400.status_code == 400
    assert "Cannot delete deployment used by" in delete_response_400.json()["detail"]

    # Delete the function, then retry deleting the deployment
    function_id = function_response.json()["id"]
    await client.delete(f"/hpc/functions/{function_id}")

    # Deletion should now succeed
    delete_response_200 = await client.delete(f"/hpc/deployments/{deployment_id}")
    assert delete_response_200.status_code == 200
    assert "Successfully deleted" in delete_response_200.json()["detail"]

    # Verify the deployment is gone
    get_response = await client.get(f"/hpc/deployments/{deployment_id}")
    assert get_response.status_code == 404

    # Test deleting a non-existent deployment
    delete_response_404 = await client.delete("/hpc/deployments/99999")
    assert delete_response_404.status_code == 404
