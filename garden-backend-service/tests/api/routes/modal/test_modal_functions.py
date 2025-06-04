import pytest

from tests.utils import post_modal_app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_function(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
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
    assert get_function_data["hardware_spec"] is not None
    assert get_function_data["num_invocations"] is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_functions(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # Create a modal app which adds a modal function
    create_app_response = await post_modal_app(
        client, mock_modal_app_create_request_one_function
    )

    # Test getting all modal functions
    response = await client.get("/modal-functions")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) >= 1

    # Test filtering by ID
    created_function_id = create_app_response["modal_functions"][0]["id"]
    response = await client.get(f"/modal-functions?id={created_function_id}")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["id"] == created_function_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_functions_with_tags(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # Create a modal app with a function that has tags
    app_data = mock_modal_app_create_request_one_function.copy()
    app_data["modal_functions"][0]["tags"] = ["tag1", "tag2"]

    await post_modal_app(client, app_data)

    # Test filtering by tag
    response = await client.get("/modal-functions?tags=tag1")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) >= 1
    assert "tag1" in response_data[0]["tags"]

    # Test filtering by non-existent tag
    response = await client.get("/modal-functions?tags=non-existent-tag")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_functions_with_draft(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # Create a modal app with a function (draft by default since doi is null)
    await post_modal_app(client, mock_modal_app_create_request_one_function)

    # Test filtering by draft status
    response = await client.get("/modal-functions?draft=true")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) >= 1
    assert response_data[0]["doi"] is None

    # Test filtering by published status
    response = await client.get("/modal-functions?draft=false")
    assert response.status_code == 200
    response_data = response.json()
    # Should be empty since all functions are drafts
    assert len(response_data) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_modal_function_partial_update(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
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
    assert set(patched_data["tags"]) == set(["Some", "New", "Tags"])
