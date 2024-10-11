import pytest

from tests.utils import post_modal_app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_function(
    override_modal_vip,
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    create_app_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    child_function = create_app_response["modal_functions"][0]
    get_function_response = await client.get(f"/modal-functions/{child_function['id']}")
    assert get_function_response.status_code == 200
    get_function_data = get_function_response.json()
    assert (
        get_function_data["title"]
        == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_function_partial_update(
    override_modal_vip,
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_sandboxed_functions,
    mock_modal_app_create_request_one_function,
):
    create_app_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    # Update the Modal Function
    created_function_id = create_app_response["modal_functions"][0]["id"]
    new_tags = {"tags": ["Some", "New", "Tags"]}
    patch_response = await client.patch(
        f"/modal-functions/{created_function_id}", json=new_tags
    )
    assert patch_response.status_code == 200
    patched_data = patch_response.json()
    assert patched_data["tags"] == new_tags["tags"]
