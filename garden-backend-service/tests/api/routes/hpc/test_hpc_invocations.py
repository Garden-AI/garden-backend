import pytest


async def create_hpc_endpoint(client, create_hpc_endpoint_json):
    response = await client.post("/hpc/endpoints", json=create_hpc_endpoint_json)
    assert response.status_code == 200
    return response.json()


async def create_hpc_deployment(client, create_hpc_deployment_json):
    response = await client.post("/hpc/deployments", json=create_hpc_deployment_json)
    assert response.status_code == 200
    return response.json()


async def create_hpc_function(client, create_hpc_function_json, deployment_id):
    create_hpc_function_json["deployment_ids"] = [deployment_id]
    response = await client.post("/hpc/functions", json=create_hpc_function_json)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_hpc_invocation(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_endpoint_json,
    create_hpc_deployment_json,
    create_hpc_function_json,
):
    # Set up test data
    endpoint = await create_hpc_endpoint(client, create_hpc_endpoint_json)
    deployment = await create_hpc_deployment(client, create_hpc_deployment_json)
    function = await create_hpc_function(
        client, create_hpc_function_json, deployment["id"]
    )

    # Create invocation log
    invocation_request = {
        "function_id": function["id"],
        "hpc_endpoint_id": endpoint["id"],
        "globus_task_id": "550e8400-e29b-41d4-a716-446655440001",
        "user_endpoint_config": {"key": "value"},
    }

    create_response = await client.post("/hpc/invocations", json=invocation_request)
    assert create_response.status_code == 200
    created_data = create_response.json()
    assert created_data["function_id"] == function["id"]
    assert created_data["hpc_endpoint_id"] == endpoint["id"]
    assert created_data["globus_task_id"] == invocation_request["globus_task_id"]
    assert created_data["user_endpoint_config"] == {"key": "value"}
    assert "id" in created_data
    assert "date_invoked" in created_data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_hpc_invocations(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_endpoint_json,
    create_hpc_deployment_json,
    create_hpc_function_json,
):
    # Set up test data
    endpoint = await create_hpc_endpoint(client, create_hpc_endpoint_json)
    deployment = await create_hpc_deployment(client, create_hpc_deployment_json)
    function = await create_hpc_function(
        client, create_hpc_function_json, deployment["id"]
    )

    # Create two invocation logs
    invocation_request_1 = {
        "function_id": function["id"],
        "hpc_endpoint_id": endpoint["id"],
        "globus_task_id": "550e8400-e29b-41d4-a716-446655440001",
        "user_endpoint_config": {},
    }
    invocation_request_2 = {
        "function_id": function["id"],
        "hpc_endpoint_id": endpoint["id"],
        "globus_task_id": "550e8400-e29b-41d4-a716-446655440002",
        "user_endpoint_config": {},
    }

    await client.post("/hpc/invocations", json=invocation_request_1)
    await client.post("/hpc/invocations", json=invocation_request_2)

    # Get all invocations
    get_response = await client.get("/hpc/invocations")
    assert get_response.status_code == 200
    invocations = get_response.json()
    assert len(invocations) == 2
    assert invocations[0]["function_id"] == function["id"]
    assert invocations[1]["function_id"] == function["id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_invocation_nonexistent_function(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_endpoint_json,
):
    endpoint = await create_hpc_endpoint(client, create_hpc_endpoint_json)

    invocation_request = {
        "function_id": 99999,
        "hpc_endpoint_id": endpoint["id"],
        "globus_task_id": "550e8400-e29b-41d4-a716-446655440001",
        "user_endpoint_config": {},
    }

    create_response = await client.post("/hpc/invocations", json=invocation_request)
    assert create_response.status_code == 404
    assert "HPC Function not found" in create_response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_invocation_nonexistent_endpoint(
    client,
    mock_db_session,
    override_authenticated_dependency,
    create_hpc_deployment_json,
    create_hpc_function_json,
):
    deployment = await create_hpc_deployment(client, create_hpc_deployment_json)
    function = await create_hpc_function(
        client, create_hpc_function_json, deployment["id"]
    )

    invocation_request = {
        "function_id": function["id"],
        "hpc_endpoint_id": 99999,
        "globus_task_id": "550e8400-e29b-41d4-a716-446655440001",
        "user_endpoint_config": {},
    }

    create_response = await client.post("/hpc/invocations", json=invocation_request)
    assert create_response.status_code == 404
    assert "HPC Endpoint not found" in create_response.json()["detail"]
