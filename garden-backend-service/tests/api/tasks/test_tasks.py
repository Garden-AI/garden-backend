from unittest.mock import patch

import pytest
from src.api.tasks import SearchIndexUpdateError
from tests.utils import post_entrypoints


@pytest.mark.asyncio
@pytest.mark.integration
async def test_failed_create_request(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency_with_sync,
    mock_garden_create_request_no_entrypoints_json,
):

    with patch(
        "src.api.tasks.tasks._create_or_update_on_search_index",
        side_effect=SearchIndexUpdateError("INTENTIONAL ERROR FOR TESTING", ""),
    ) as mock_create:
        # Posting a new garden should succeed, but should log a failed update
        post_response = await client.post(
            "/gardens", json=mock_garden_create_request_no_entrypoints_json
        )
        assert post_response.status_code == 200
        mock_create.assert_called_once()

        # Look for the failed update...
        failed_update_response = await client.get("/status/failed-updates")
        assert failed_update_response.status_code == 200
        data = failed_update_response.json()
        assert len(data) == 1
        assert data[0]["doi"] == mock_garden_create_request_no_entrypoints_json["doi"]
        assert data[0]["error_message"] == "INTENTIONAL ERROR FOR TESTING"
        assert data[0]["operation_type"] == "create_or_update"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_failed_garden_update(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency_with_sync,
    mock_garden_create_request_no_entrypoints_json,
):
    with patch(
        "src.api.tasks.tasks._create_or_update_on_search_index",
        side_effect=[None, SearchIndexUpdateError("INTENTIONAL ERROR FOR TESTING", "")],
    ) as mock_create:
        # Posting a new garden should succeed
        post_response = await client.post(
            "/gardens", json=mock_garden_create_request_no_entrypoints_json
        )
        assert post_response.status_code == 200
        mock_create.assert_called_once()

        # Updating the garden data should succeed, but should log a failed update
        doi = mock_garden_create_request_no_entrypoints_json["doi"]
        mock_garden_create_request_no_entrypoints_json["authors"] = [
            "Some",
            "New",
            "Authors",
        ]
        mock_create.reset_mock()
        put_response = await client.put(
            f"/gardens/{doi}", json=mock_garden_create_request_no_entrypoints_json
        )
        assert put_response.status_code == 200
        mock_create.assert_called_once()

        failed_updates_response = await client.get("/status/failed-updates")
        assert failed_updates_response.status_code == 200
        data = failed_updates_response.json()
        assert len(data) == 1
        assert data[0]["doi"] == doi
        assert data[0]["error_message"] == "INTENTIONAL ERROR FOR TESTING"
        assert data[0]["operation_type"] == "create_or_update"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_failed_delete_request(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency_with_sync,
    mock_garden_create_request_no_entrypoints_json,
):
    with patch(
        "src.api.tasks.tasks._create_or_update_on_search_index",
        side_effect=None,
    ):
        # Posting a new garden should succeed
        doi = mock_garden_create_request_no_entrypoints_json["doi"]
        post_response = await client.post(
            "/gardens", json=mock_garden_create_request_no_entrypoints_json
        )
        assert post_response.status_code == 200

        with patch(
            "src.api.tasks.tasks._delete_from_search_index",
            side_effect=SearchIndexUpdateError("INTENTIONAL ERROR FOR TESTING", ""),
        ):
            # Deleting the garden should succeed, but should log a failed update
            delete_response = await client.delete(f"/gardens/{doi}")
            assert delete_response.status_code == 200

            failed_delete_response = await client.get("/status/failed-updates")
            failed_delete_response.status_code == 200
            data = failed_delete_response.json()
            assert len(data) == 1
            assert (
                data[0]["doi"] == mock_garden_create_request_no_entrypoints_json["doi"]
            )
            assert data[0]["error_message"] == "INTENTIONAL ERROR FOR TESTING"
            assert data[0]["operation_type"] == "delete"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_failed_entrypoint_update(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency_with_sync,
    create_entrypoint_with_related_metadata_json,
    create_shared_entrypoint_json,
    create_garden_two_entrypoints_json,
):

    with patch(
        "src.api.tasks.tasks._create_or_update_on_search_index",
        side_effect=[None, SearchIndexUpdateError("INTENTIONAL ERROR FOR TESTING", "")],
    ):
        entrypoint_doi = create_shared_entrypoint_json["doi"]
        garden_doi = create_garden_two_entrypoints_json["doi"]

        # Post an entrypoint and an associated garden
        await post_entrypoints(
            client,
            create_shared_entrypoint_json,
            create_entrypoint_with_related_metadata_json,
        )
        post_response = await client.post(
            "/gardens", json=create_garden_two_entrypoints_json
        )
        assert post_response.status_code == 200

        # Update the entrypoint
        create_shared_entrypoint_json["tags"] = ["Some", "New", "Tags"]
        put_response = await client.put(
            f"/entrypoints/{entrypoint_doi}", json=create_shared_entrypoint_json
        )
        assert put_response.status_code == 200

        # The update should have triggered a failed update
        failed_update_response = await client.get("/status/failed-updates")
        assert failed_update_response.status_code == 200
        data = failed_update_response.json()
        assert len(data) == 1
        assert data[0]["doi"] == garden_doi
        assert data[0]["operation_type"] == "create_or_update"
