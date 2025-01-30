import asyncio
import base64
from typing import Any, Dict

import pytest
from httpx import AsyncClient

from src.api.schemas.modal.invocations import ModalInvocationRequest
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
) -> Dict[str, Any]:
    """Helper function to create a modal app deployment request"""
    # Use the mock request as base and override specific fields
    request_data = mock_modal_app_create_request_one_function.copy()
    request_data["app_name"] = app_name

    function_name = request_data["modal_functions"][0]["function_name"]

    # Create new file contents with matching app name and function name
    file_contents = create_modal_file_contents(app_name, function_name)
    request_data["file_contents"] = file_contents

    response = await client.post("/modal-apps/async", json=request_data)
    assert response.status_code == 200
    return response.json()


async def get_modal_app(client: AsyncClient, app_id: int) -> Dict[str, Any]:
    """Helper function to get modal app details"""
    response = await client.get(f"/modal-apps/{app_id}")
    assert response.status_code == 200
    return response.json()


async def wait_for_deployment_status(
    client: AsyncClient,
    app_id: int,
    target_status: str,
    timeout_seconds: float = 15.0,
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


async def create_modal_invocation_request(
    client: AsyncClient,
    function_id: int,
    args_kwargs_serialized: bytes = b"mock_input_data",
) -> Dict[str, Any]:
    """Helper function to create a modal invocation request"""
    request_data = ModalInvocationRequest(
        function_id=function_id,
        args_kwargs_serialized=args_kwargs_serialized,
    ).model_dump()
    response = await client.post("/modal-invocations/async", json=request_data)
    assert response.status_code == 200
    return response.json()


async def wait_for_invocation_status(
    client: AsyncClient,
    invocation_id: int,
    target_status: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.5,
) -> Dict[str, Any]:
    """Wait for a modal invocation to reach the target status"""
    start_time = asyncio.get_event_loop().time()
    while True:
        response = await client.get(f"/modal-invocations/{invocation_id}")
        assert response.status_code == 200
        invocation = response.json()

        if invocation["status"] == target_status:
            return invocation

        if asyncio.get_event_loop().time() - start_time > timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for invocation {invocation_id} to reach status {target_status}. "
                f"Current status: {invocation['status']}"
            )

        await asyncio.sleep(poll_interval_seconds)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_modal_deployments(
    modal_deployment_environment: dict[str, Any],
    num_concurrent_requests: int,
):
    """Test that multiple Modal apps can be deployed concurrently"""
    env = modal_deployment_environment
    client = env["client"]
    mocker = env["mocker"]

    # Mock the deployment and validation functions
    mocker.patch(
        "src.api.dependencies.sandboxed_functions.deploy_modal_app",
        side_effect=lambda config: asyncio.sleep(2.0),  # Simulate deployment time
    )
    mocker.patch(
        "src.api.dependencies.sandboxed_functions.validate_modal_file",
        return_value={
            "functions": {"predict_iris_type": {"cpu": 0.1, "memory": 256, "gpu": None}}
        },
    )

    # Create multiple apps concurrently
    app_creation_tasks = [
        create_modal_app_request(client, f"app-{i}", env["app_request"])
        for i in range(num_concurrent_requests)
    ]

    # Wait for all apps to be created
    created_apps = await asyncio.gather(*app_creation_tasks)

    # Verify all creations were successful and get app IDs
    app_ids = []
    for app_data in created_apps:
        assert app_data["deploy_status"] == AsyncModalJobStatus.PENDING.value
        app_ids.append(app_data["id"])

    # Wait for all deployments to complete concurrently
    deployment_tasks = [
        wait_for_deployment_status(
            client,
            app_id,
            AsyncModalJobStatus.DONE.value,
            timeout_seconds=10.0,
        )
        for app_id in app_ids
    ]

    # Wait for all deployments to finish
    final_apps = await asyncio.gather(*deployment_tasks)

    # Verify all deployments completed successfully
    for app in final_apps:
        assert app["deploy_status"] == AsyncModalJobStatus.DONE.value
        assert app["deploy_error"] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_modal_invocations(
    modal_deployment_environment: dict[str, Any],
    num_concurrent_requests: int,
):
    """Test that multiple Modal functions can be invoked concurrently"""
    env = modal_deployment_environment
    client = env["client"]
    mocker = env["mocker"]

    # Create a modal app with a function to invoke
    response = await client.post("/modal-apps", json=env["app_request"])
    assert response.status_code == 200
    response_data = response.json()
    function_id = response_data["modal_function_ids"][0]

    # Mock the modal function lookup and invocation
    mocker.patch("modal.functions._Function.lookup", return_value=env["mock_function"])
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=env["mock_invocation"],
    )

    # Create multiple invocations concurrently
    invocation_tasks = [
        create_modal_invocation_request(client, function_id)
        for _ in range(num_concurrent_requests)
    ]

    # Wait for all invocations to be created
    created_invocations = await asyncio.gather(*invocation_tasks)

    # Verify all creations were successful and get invocation IDs
    invocation_ids = []
    for invocation_data in created_invocations:
        assert invocation_data["status"] == AsyncModalJobStatus.PENDING.value
        invocation_ids.append(invocation_data["id"])

    # Wait for all invocations to complete concurrently
    completion_tasks = [
        wait_for_invocation_status(
            client,
            invocation_id,
            AsyncModalJobStatus.DONE.value,
            timeout_seconds=10.0,
        )
        for invocation_id in invocation_ids
    ]

    # Wait for all invocations to finish
    final_invocations = await asyncio.gather(*completion_tasks)

    # Verify all invocations completed successfully
    for invocation in final_invocations:
        assert invocation["status"] == AsyncModalJobStatus.DONE.value
        assert invocation["result"]["data"] == base64.b64encode(b"mock_result").decode(
            "utf-8"
        )
