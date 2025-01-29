import asyncio
from typing import Any, Dict

import pytest
from httpx import AsyncClient


def create_modal_file_contents(app_name: str, function_name: str) -> str:
    """Create Modal file contents with matching app name and function name"""
    return f"""
import modal

app = modal.App(name="{app_name}", image=modal.Image.debian_slim(python_version="3.12"))

@app.function()
def {function_name}():
    return "Hello from Modal!"
"""


async def create_modal_app_request(
    client: AsyncClient,
    app_name: str,
    mock_modal_app_create_request_one_function: Dict[str, Any],
):
    """Helper function to create a modal app deployment request"""
    # Use the mock request as base and override specific fields
    request_data = mock_modal_app_create_request_one_function.copy()
    function_name = request_data["modal_functions"][0]["function_name"]

    # Update app name and file contents consistently
    request_data["app_name"] = app_name
    request_data["file_contents"] = create_modal_file_contents(app_name, function_name)
    return await client.post("/modal-apps/async", json=request_data)


async def get_modal_app(client: AsyncClient, app_id: int) -> Dict[str, Any]:
    """Helper function to get modal app details"""
    response = await client.get(f"/modal-apps/{app_id}")
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_modal_deployments(
    client: AsyncClient,
    mock_db_session,
    mock_auth_state,
    override_authenticated_dependency,
    override_sandboxed_functions,
    override_publisher_group_membership,
    mock_modal_app_create_request_one_function,
):
    """Test that multiple concurrent modal deployments work correctly"""
    num_concurrent = 10
    tasks = []

    for i in range(num_concurrent):
        app_name = f"test-app-{i}"
        tasks.append(
            create_modal_app_request(
                client,
                app_name,
                mock_modal_app_create_request_one_function,
            )
        )

    try:
        responses = await asyncio.gather(*tasks)
        for i, response in enumerate(responses):
            print(f"Response {i}: {response.status_code}")
            assert response.status_code == 200

        # Verify each response has a unique app ID
        app_ids = [response.json()["id"] for response in responses]
        assert len(set(app_ids)) == num_concurrent

        # Verify app states
        get_tasks = [get_modal_app(client, app_id) for app_id in app_ids]
        apps = await asyncio.gather(*get_tasks)

        # All apps should be in either pending or done state
        for app in apps:
            assert app["deploy_status"] in ["pending", "done"]

    except Exception as e:
        print(f"Error during concurrent requests: {str(e)}")
        raise
