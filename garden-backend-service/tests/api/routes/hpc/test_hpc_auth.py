import pytest
from fastapi import status

from src.api.dependencies.auth import authenticated
from src.main import app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hpc_endpoints_unauthenticated(
    client,
    mock_db_session,
    override_get_settings_dependency,
):
    """Test that unauthenticated users receive a 403 Forbidden error."""
    # Test PATCH and DELETE on deployments
    patch_deployment_response = await client.patch("/hpc/deployments/1", json={})
    assert patch_deployment_response.status_code == status.HTTP_403_FORBIDDEN

    delete_deployment_response = await client.delete("/hpc/deployments/1")
    assert delete_deployment_response.status_code == status.HTTP_403_FORBIDDEN

    # Test PATCH and DELETE on endpoints
    patch_endpoint_response = await client.patch("/hpc/endpoints/1", json={})
    assert patch_endpoint_response.status_code == status.HTTP_403_FORBIDDEN

    delete_endpoint_response = await client.delete("/hpc/endpoints/1")
    assert delete_endpoint_response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hpc_admin_endpoints_non_admin(
    client,
    mock_db_session,
    override_authenticated_dependency,  # Regular user, not superuser
    override_get_settings_dependency,
):
    """Test that non-admin users receive a 403 Forbidden error on admin endpoints."""
    # Test PATCH and DELETE on deployments
    patch_deployment_response = await client.patch("/hpc/deployments/1", json={})
    assert patch_deployment_response.status_code == status.HTTP_403_FORBIDDEN

    delete_deployment_response = await client.delete("/hpc/deployments/1")
    assert delete_deployment_response.status_code == status.HTTP_403_FORBIDDEN

    # Test PATCH and DELETE on endpoints
    patch_endpoint_response = await client.patch("/hpc/endpoints/1", json={})
    assert patch_endpoint_response.status_code == status.HTTP_403_FORBIDDEN

    delete_endpoint_response = await client.delete("/hpc/endpoints/1")
    assert delete_endpoint_response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hpc_function_non_owner(
    client,
    mock_db_session,
    mock_auth_state,  # The owner
    mock_auth_state_other_user,  # The other user
    create_hpc_function_json,
    create_hpc_deployment_json,
    create_hpc_endpoint_json,
    override_get_settings_dependency,
):
    """Test that non-owners receive a 403 Forbidden error when modifying a function."""
    # Create endpoint, deployment, and function as the first user
    app.dependency_overrides[authenticated] = lambda: mock_auth_state
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

    create_hpc_function_json["deployment_ids"] = [deployment["id"]]
    function_response = await client.post(
        "/hpc/functions", json=create_hpc_function_json
    )
    assert function_response.status_code == 200
    function_id = function_response.json()["id"]

    # Switch to the other user
    app.dependency_overrides[authenticated] = lambda: mock_auth_state_other_user

    # Try to PATCH and DELETE the function as the other user
    patch_function_response = await client.patch(
        f"/hpc/functions/{function_id}", json={"tags": ["new"]}
    )
    assert patch_function_response.status_code == status.HTTP_401_UNAUTHORIZED

    delete_function_response = await client.delete(f"/hpc/functions/{function_id}")
    assert delete_function_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Clean up only the authenticated override (don't clear all overrides!)
    del app.dependency_overrides[authenticated]
