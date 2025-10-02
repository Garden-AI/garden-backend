import pytest


async def create_hpc_deployment(client, create_hpc_deployment_json):
    response = await client.post("/hpc/deployments", json=create_hpc_deployment_json)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_and_get_hpc_function(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_function_json,
    create_hpc_deployment_json,
):
    deployment = await create_hpc_deployment(client, create_hpc_deployment_json)
    create_hpc_function_json["deployment_ids"] = [deployment["id"]]

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
    create_hpc_deployment_json,
):
    deployment = await create_hpc_deployment(client, create_hpc_deployment_json)
    create_hpc_function_json["deployment_ids"] = [deployment["id"]]

    create_response = await client.post("/hpc/functions", json=create_hpc_function_json)
    function_id = create_response.json()["id"]

    patch_response = await client.patch(
        f"/hpc/functions/{function_id}", json={"tags": ["updated"]}
    )
    assert patch_response.status_code == 200
    assert "updated" in patch_response.json()["tags"]
