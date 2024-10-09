import pytest

from tests.utils import post_modal_app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app(
    client,
    mock_db_session,
    override_authenticated_dependency,
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
        == mock_modal_app_create_request_one_function["app_name"]
    )
    assert (
        response_data["modal_functions"][0]["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_app(
    client,
    mock_db_session,
    override_authenticated_dependency,
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
        == mock_modal_app_create_request_one_function["app_name"]
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
    override_authenticated_dependency,
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
