from copy import deepcopy
from unittest.mock import patch

import pytest
from src.api.dependencies.auth import authenticated
from src.main import app
from tests.utils import post_modal_app

@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_modal_app_create_request_one_function,
    override_validate_modal_file_dependency,
    override_deploy_modal_app_dependency,
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
    override_validate_modal_file_dependency,
    override_deploy_modal_app_dependency,
):  
    post_response = await post_modal_app(client, mock_modal_app_create_request_one_function)
    
    get_response = await client.get(f"/modal_apps/{post_response['id']}")
    assert get_response.status_code == 200
    get_response_data = get_response.json()
    assert get_response_data["app_name"] == mock_modal_app_create_request_one_function["app_name"]
    assert get_response_data["modal_functions"][0]["title"] == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]
