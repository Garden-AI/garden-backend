import pytest

from src.api.routes.modal.modal_apps import _generate_app_name
from tests.utils import post_modal_app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["app_name"].startswith(
        f"{mock_modal_publisher_auth_state.identity_id}-"
        + mock_modal_app_create_request_one_function["app_name"]
    )
    assert (
        response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )


@pytest.mark.parametrize(
    "mock_validate_modal_file_provider",
    [
        {
            "app_name": "class-app",
            "functions": {
                "Model.say_hi": {"cpus": 1, "gpus": "A100", "memory": 256},
                "Model.*": {"cpus": 1, "gpus": "A100", "memory": 256},
            },
        },
    ],
    indirect=True,
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app_with_class(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_with_class,
    override_sandboxed_functions,
):
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_with_class
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["app_name"].startswith(
        f"{mock_modal_publisher_auth_state.identity_id}-"
        + mock_modal_app_create_request_with_class["app_name"]
    )
    assert (
        response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_with_class["modal_functions"][0]["title"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app_async(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_auth_state,
    mock_modal_app_create_request_one_function,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    response = await client.post(
        "/modal-apps/async", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["app_name"].startswith(
        f"{mock_auth_state.identity_id}-"
        + mock_modal_app_create_request_one_function["app_name"]
    )
    assert (
        response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )

    assert response_data["deploy_status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app_async_resolves_on_success(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_auth_state,
    mock_modal_app_create_request_one_function,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    response = await client.post(
        "/modal-apps/async", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["deploy_status"] == "pending"

    get_response = await client.get(f"/modal-apps/{response_data['id']}")
    assert get_response.status_code == 200
    get_response_data = get_response.json()
    assert get_response_data["deploy_status"] == "done"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_app(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    post_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    get_response = await client.get(f"/modal-apps/{post_response['id']}")
    assert get_response.status_code == 200
    get_response_data = get_response.json()
    assert get_response_data["app_name"].startswith(
        f"{mock_modal_publisher_auth_state.identity_id}-"
        + mock_modal_app_create_request_one_function["app_name"]
    )
    assert (
        get_response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_apps(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    num_apps = 5
    for _ in range(num_apps):
        await post_modal_app(client, mock_modal_app_create_request_one_function)

    get_response = await client.get("/modal-apps/")
    assert get_response.status_code == 200
    get_response_data = get_response.json()
    assert len(get_response_data) == num_apps


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_modal_app(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
    mocker,
    override_get_modal_client_dependency,
    override_get_settings_dependency,
):
    post_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    app_id = post_response["id"]

    mock_stop_app = mocker.patch("src.api.routes.modal.modal_apps._stop_modal_app")

    delete_response = await client.delete(f"/modal-apps/{app_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "detail": f"Successfully deleted modal app with id {app_id}."
    }

    # Verify deletion is idempotent
    response = await client.delete(f"/modal-apps/{app_id}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No Modal App found with id {app_id}."}

    # Verify _stop_modal_app was not called again for non-existent app
    mock_stop_app.assert_called_once()


def test_generate_app_names(mock_auth_state):
    user = mock_auth_state
    size_limit = 64
    num_to_gen = 100

    # maximum app name length on modal
    app_name = "a" * size_limit
    # generate a bunch of names using the same user and app name
    generated_names = [_generate_app_name(user, app_name) for _ in range(num_to_gen)]

    # assert they are all within the size limit
    assert all(map(lambda app_name: len(app_name) <= size_limit, generated_names))

    # assert there are no duplicates
    assert len(set(generated_names)) == num_to_gen


@pytest.mark.parametrize(
    "mock_validate_modal_file_provider",
    [
        {
            "app_name": "test-app",
            "functions": {
                "hello": {"cpus": 1, "gpus": "A100", "memory": 256},
                "goodbye": {"cpus": 1, "gpus": "A100", "memory": 256},
            },
        },
    ],
    indirect=True,
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_app_name_mismatch(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    # First create an app with a known name
    initial_app = """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"
"""
    # Get metadata for the initial app
    metadata_response = await client.post(
        "/modal-file-metadata", json={"file_contents": initial_app}
    )
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()

    # Create the app using the metadata directly
    create_response = await post_modal_app(client, metadata)
    app_id = create_response["id"]

    # Try to patch with a different app name in the source code
    patch_data = {
        "file_contents": """
import modal

app = modal.App(name="different-app-name")

@app.function()
def hello():
    return "Hello, world!"
"""
    }
    response = await client.patch(f"/modal-apps/async/{app_id}", json=patch_data)
    assert response.status_code == 400
    assert "App name mismatch" in response.json()["detail"]


@pytest.mark.parametrize(
    "mock_validate_modal_file_provider",
    [
        {
            "app_name": "test-app",
            "functions": {
                "hello": {"cpus": 1, "gpus": "A100", "memory": 256},
                "goodbye": {"cpus": 1, "gpus": "A100", "memory": 256},
            },
        },
    ],
    indirect=True,
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_app_remove_function(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    # First create an app with multiple functions
    initial_app = """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"

@app.function()
def goodbye():
    return "Goodbye, world!"
"""
    # Get metadata for the initial app
    metadata_response = await client.post(
        "/modal-file-metadata", json={"file_contents": initial_app}
    )
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()

    # Create the app using the metadata directly
    create_response = await post_modal_app(client, metadata)
    app_id = create_response["id"]

    # Try to patch by removing one of the functions
    patch_data = {
        "file_contents": """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"
"""
    }
    response = await client.patch(f"/modal-apps/async/{app_id}", json=patch_data)
    assert response.status_code == 400
    assert (
        "Function names (goodbye) not found in the updated Modal file"
        in response.json()["detail"]
    )


@pytest.mark.parametrize(
    "mock_validate_modal_file_provider",
    [
        {
            "app_name": "test-app",
            "functions": {
                "hello": {"cpus": 1, "gpus": "A100", "memory": 256},
                "goodbye": {"cpus": 1, "gpus": "A100", "memory": 256},
            },
        },
    ],
    indirect=True,
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_app_add_function(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    # First create an app with one function
    initial_app = """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"
"""
    # Get metadata for the initial app
    metadata_response = await client.post(
        "/modal-file-metadata", json={"file_contents": initial_app}
    )
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()

    # Create the app using the metadata directly
    create_response = await post_modal_app(client, metadata)
    app_id = create_response["id"]

    # Patch to add a new function
    patch_data = {
        "file_contents": """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"

@app.function()
def goodbye():
    return "Goodbye, world!"
"""
    }
    response = await client.patch(f"/modal-apps/async/{app_id}", json=patch_data)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data["modal_functions"]) == 2
    assert any(
        fn["function_name"] == "goodbye" for fn in response_data["modal_functions"]
    )


@pytest.mark.parametrize(
    "mock_validate_modal_file_provider",
    [
        {
            "app_name": "test-app",
            "functions": {
                "hello": {"cpus": 1, "gpus": "A100", "memory": 256},
            },
        },
    ],
    indirect=True,
)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_app_modify_function(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_sandboxed_functions,
):
    # First create an app
    initial_app = """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, world!"
"""
    # Get metadata for the initial app
    metadata_response = await client.post(
        "/modal-file-metadata", json={"file_contents": initial_app}
    )
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()

    # Create the app using the metadata directly
    create_response = await post_modal_app(client, metadata)
    app_id = create_response["id"]

    # Patch to modify the function
    patch_data = {
        "file_contents": """
import modal

app = modal.App(name="test-app")

@app.function()
def hello():
    return "Hello, modified world!"
"""
    }
    response = await client.patch(f"/modal-apps/async/{app_id}", json=patch_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["deploy_status"] == "pending"
