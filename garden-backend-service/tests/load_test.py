import asyncio
from typing import Any, Dict

import pytest
from httpx import AsyncClient

from src.modal.status import AsyncModalJobStatus


def create_modal_file_contents(app_name: str, function_name: str) -> str:
    """Create Modal file contents with matching app name and function name"""
    return f"""
import modal

app = modal.App(name="{app_name}", image=modal.Image.debian_slim(python_version="3.12"))

@app.function()
def {function_name}():
    return "Hello from Modal!"
"""


def create_delayed_deploy_function(delay_seconds: float):
    """Create a deployment function that simulates a long-running deployment"""

    async def delayed_deploy(deploy_config: Dict[str, Any]):
        await asyncio.sleep(delay_seconds)
        return {}  # Mock successful deployment

    return delayed_deploy


async def mock_deploy(config: dict[str, str | bytes]) -> None:
    await asyncio.sleep(2.0)  # Simulate deployment time
    return None


async def mock_validate_modal_file(
    args: dict[str, str],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Mock the validate_modal_file function to return hardware specs"""
    return {
        "functions": {"predict_iris_type": {"cpu": 0.1, "memory": 256, "gpu": None}}
    }


async def create_modal_app_request(
    client: AsyncClient,
    app_name: str,
    mock_modal_app_create_request_one_function: Dict[str, Any],
):
    """Helper function to create a modal app deployment request"""
    # Use the mock request as base and override specific fields
    request_data = mock_modal_app_create_request_one_function.copy()
    request_data["app_name"] = app_name

    # Get the function name from the request data
    function_name = request_data["modal_functions"][0]["function_name"]

    # Create new file contents with matching app name and function name
    file_contents = create_modal_file_contents(app_name, function_name)
    request_data["file_contents"] = file_contents

    return await client.post("/modal-apps/async", json=request_data)


async def get_modal_app(client: AsyncClient, app_id: int) -> Dict[str, Any]:
    """Helper function to get modal app details"""
    response = await client.get(f"/modal-apps/{app_id}")
    assert response.status_code == 200
    return response.json()


async def wait_for_deployment_status(
    client: AsyncClient,
    app_id: int,
    target_status: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.5,
) -> Dict[str, Any]:
    """Wait for a modal app to reach the target deployment status"""
    start_time = asyncio.get_event_loop().time()
    while True:
        app = await get_modal_app(client, app_id)
        if app["deploy_status"] == target_status:
            return app

        if asyncio.get_event_loop().time() - start_time > timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for app {app_id} to reach status {target_status}. "
                f"Current status: {app['deploy_status']}"
            )

        await asyncio.sleep(poll_interval_seconds)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_modal_deployments(
    client: AsyncClient,
    monkeypatch,
    override_publisher_group_membership,
    override_authenticated_dependency,
    override_sandboxed_functions,
    override_get_settings_dependency,
    mock_db_session,
    mock_auth_state,
    mock_modal_app_create_request_one_function,
):
    # Mock the deployment and validation functions
    monkeypatch.setattr(
        "src.api.dependencies.sandboxed_functions.deploy_modal_app", mock_deploy
    )
    monkeypatch.setattr(
        "src.api.dependencies.sandboxed_functions.validate_modal_file",
        mock_validate_modal_file,
    )

    # Create multiple apps concurrently
    num_apps = 30
    app_creation_tasks = []
    for i in range(num_apps):
        app_name = f"app-{i}"
        task = create_modal_app_request(
            client, app_name, mock_modal_app_create_request_one_function
        )
        app_creation_tasks.append(task)

    # Wait for all apps to be created
    responses = await asyncio.gather(*app_creation_tasks)

    # Verify all creations were successful and get app IDs
    app_ids = []
    for response in responses:
        assert response.status_code == 200
        app_data = response.json()
        assert app_data["deploy_status"] == AsyncModalJobStatus.PENDING.value
        app_ids.append(app_data["id"])

    # Wait for all deployments to complete concurrently
    deployment_tasks = []
    for app_id in app_ids:
        task = wait_for_deployment_status(
            client,
            app_id,
            AsyncModalJobStatus.DONE.value,
            timeout_seconds=10.0,  # Longer timeout for concurrent deployments
        )
        deployment_tasks.append(task)

    # Wait for all deployments to finish
    final_apps = await asyncio.gather(*deployment_tasks)

    # Verify all deployments completed successfully
    for app in final_apps:
        assert app["deploy_status"] == AsyncModalJobStatus.DONE.value
        assert app["deploy_error"] is None
