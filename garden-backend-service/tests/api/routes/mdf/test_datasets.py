import pytest
from src.api.dependencies.database import get_db_session
from src.main import app


@pytest.mark.asyncio
async def test_add_pending_dataset(
    client,
    override_get_settings_dependency_with_mdf_polling,
    override_mdf_authenticated_dependency,
    override_get_db_session,
    mocker,
):
    mock_db_session = app.dependency_overrides[get_db_session]()

    flow_action_id = "c42c4f90-536a-4cfc-9e12-7292a00079cc"
    request = {
        "flow_action_id": flow_action_id,
        "versioned_source_id": "a_versioned_source_id",
        "owner_identity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    response = await client.put("/mdf/create", json=request)
    assert response.status_code == 200

    response_data = response.json()
    assert response_data == {
        "detail": f"Added flow {flow_action_id} to background tasks."
    }

    mock_db_session.add.assert_called_once()
    added_object = mock_db_session.add.call_args[0][0]
    assert str(added_object.flow_action_id) == flow_action_id

    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_failed_add_pending_dataset(
    client,
    override_get_settings_dependency,
    override_mdf_authenticated_dependency,
    override_get_db_session,
    mocker,
):
    mock_db_session = app.dependency_overrides[get_db_session]()

    request = {
        "flow_action_id": "c42c4f90-536a-4cfc-9e12-7292a00079cc",
        "versioned_source_id": "a_versioned_source_id",
        "owner_identity_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    response = await client.put("/mdf/create", json=request)
    assert response.status_code == 200

    response_data = response.json()
    assert response_data == {
        "detail": "Polling MDF flows is currently turned off, did not add flow to background tasks."
    }

    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
