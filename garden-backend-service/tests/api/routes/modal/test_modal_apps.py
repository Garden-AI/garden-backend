import pytest

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
    assert (
        response_data["app_name"]
        == f"{mock_modal_publisher_auth_state.identity_id}-"
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
    assert (
        response_data["app_name"]
        == f"{mock_modal_publisher_auth_state.identity_id}-"
        + mock_modal_app_create_request_with_class["app_name"]
    )
    assert (
        response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_with_class["modal_functions"][0]["title"]
    )


@pytest.mark.parametrize("post_url", ["/modal-apps", "/modal-apps/async"])
@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app_overwrite_behavior(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
    post_url,
):
    # Post a modal app
    response = await client.post(
        post_url,
        json=mock_modal_app_create_request_one_function,
    )
    assert response.status_code == 200

    # Default behavior is to overwrite, a second post should succeed
    response = await client.post(
        post_url,
        json=mock_modal_app_create_request_one_function,
    )
    assert response.status_code == 200

    # Forbid overwriting, another post should error
    create_request_no_overwrite = mock_modal_app_create_request_one_function
    create_request_no_overwrite["overwrite_existing"] = False
    error_response = await client.post(
        post_url,
        json=create_request_no_overwrite,
    )
    assert error_response.status_code == 409


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
    assert (
        get_response_data["app_name"]
        == f"{mock_modal_publisher_auth_state.identity_id}-"
        + mock_modal_app_create_request_one_function["app_name"]
    )
    assert (
        get_response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_modal_app(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    post_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    app_id = post_response["id"]
    delete_response = await client.delete(f"/modal-apps/{app_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "detail": f"Successfully deleted garden with id {app_id}."
    }

    # Verify deletion is idempotent
    response = await client.delete(f"/modal-apps/{app_id}")
    assert response.status_code == 200
    assert response.json() == {"detail": f"No Modal App found with id {app_id}."}
