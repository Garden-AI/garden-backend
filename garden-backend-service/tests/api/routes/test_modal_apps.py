from copy import deepcopy
from unittest.mock import patch

import pytest
from src.api.dependencies.auth import authenticated
from src.main import app

@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_modal_app(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_modal_app_create_request_one_function,
    override_get_validate_modal_file_dependency,
    override_get_deploy_modal_app_dependency
):

    response = await client.post("/modal-apps", json=mock_modal_app_create_request_one_function)
    print(f"Response content: {response.content}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["app_name"] == mock_modal_app_create_request_one_function["app_name"]
    assert response_data["modal_functions"][0]["title"] == mock_modal_app_create_request_one_function["modal_functions"][0]["title"]