from unittest.mock import AsyncMock, Mock

import globus_sdk
import httpx
import pytest
from src.api.dependencies.database import get_db_session
from src.api.tasks.mdf_tasks import (
    _add_dataset_from_completed_flow,
    _parse_doi,
    _process_active_flows,
)
from src.main import app
from src.models import PendingMDFFlow, User


@pytest.mark.asyncio
async def test_process_active_flows(
    client,
    mock_settings,
    mock_db_session,
    mocker,
):
    flow_action_id = "c42c4f90-536a-4cfc-9e12-7292a00079cc"
    mock_flow = PendingMDFFlow(
        id=1,
        flow_action_id=flow_action_id,
        versioned_source_id="a_versioned_source_id",
        owner_identity_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )

    mock_add_ds = mocker.patch(
        "src.api.tasks.mdf_tasks._add_dataset_from_completed_flow",
        new_callable=AsyncMock,
    )

    mock_auth = Mock(spec=globus_sdk.ConfidentialAppAuthClient)

    mock_flows_cli = Mock(spec=globus_sdk.FlowsClient)
    mock_flows_response = Mock(spec=globus_sdk.response.GlobusHTTPResponse)
    mock_flows_response.status_code = 200
    mock_flows_response.get.return_value = "some time"

    mock_flows_cli.get_run.return_value = mock_flows_response

    await _process_active_flows(
        [mock_flow], mock_db_session, mock_settings, mock_auth, mock_flows_cli
    )

    mock_add_ds.assert_called_once()
    added_object = mock_add_ds.call_args[0][0]
    assert added_object.flow_action_id == flow_action_id


@pytest.mark.asyncio
async def test_process_active_flows_not_complete(
    client,
    mock_settings,
    override_get_db_session,
    mocker,
):
    mock_db_session = app.dependency_overrides[get_db_session]()

    mock_flow = PendingMDFFlow(
        id=1,
        flow_action_id="c42c4f90-536a-4cfc-9e12-7292a00079cc",
        versioned_source_id="a_versioned_source_id",
        owner_identity_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        retry_count=0,
    )

    mocker.patch(
        "src.api.tasks.mdf_tasks._add_dataset_from_completed_flow",
        new_callable=AsyncMock,
    )

    mock_auth = Mock(spec=globus_sdk.ConfidentialAppAuthClient)

    mock_flows_cli = Mock(spec=globus_sdk.FlowsClient)
    mock_flows_response = Mock(spec=globus_sdk.response.GlobusHTTPResponse)
    mock_flows_response.status_code = 200
    mock_flows_response.get.return_value = None

    mock_flows_cli.get_run.return_value = mock_flows_response

    await _process_active_flows(
        [mock_flow], mock_db_session, mock_settings, mock_auth, mock_flows_cli
    )

    assert mock_flow.retry_count == 1
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_active_flows_bad_response(
    client,
    override_get_db_session,
    mock_settings,
    mocker,
):
    mock_db_session = app.dependency_overrides[get_db_session]()

    mock_flow = PendingMDFFlow(
        id=1,
        flow_action_id="c42c4f90-536a-4cfc-9e12-7292a00079cc",
        versioned_source_id="a_versioned_source_id",
        owner_identity_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        retry_count=0,
    )

    mocker.patch(
        "src.api.tasks.mdf_tasks._add_dataset_from_completed_flow",
        new_callable=AsyncMock,
    )

    mock_auth = Mock(spec=globus_sdk.ConfidentialAppAuthClient)

    mock_flows_cli = Mock(spec=globus_sdk.FlowsClient)
    mock_flows_response = Mock(spec=globus_sdk.response.GlobusHTTPResponse)
    mock_flows_response.status_code = 404
    mock_flows_response.get.return_value = None

    mock_flows_cli.get_run.return_value = mock_flows_response

    await _process_active_flows(
        [mock_flow], mock_db_session, mock_settings, mock_auth, mock_flows_cli
    )

    assert mock_flow.retry_count == 1
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_dataset_from_completed_flow(
    client,
    override_get_db_session,
    mock_settings,
    mocker,
):
    mock_db_session = app.dependency_overrides[get_db_session]()

    flow_action_id = "c42c4f90-536a-4cfc-9e12-7292a00079cc"
    versioned_source_id = "a_versioned_source_id"
    owner_identity_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    doi = "a_doi"

    mock_flow = PendingMDFFlow(
        id=1,
        flow_action_id=flow_action_id,
        versioned_source_id=versioned_source_id,
        owner_identity_id=owner_identity_id,
    )
    mock_flow_get = mocker.patch(
        "src.models.PendingMDFFlow.get", new_callable=AsyncMock
    )
    mock_flow_get.return_value = mock_flow

    mock_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": "a_source_id",
                "@version": "2019-08-27",
                "entries": [
                    {
                        "content": {
                            "dc": {
                                "identifier": {
                                    "identifier": doi,
                                    "identifierType": "DOI",
                                }
                            }
                        }
                    }
                ],
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    mock_query_search = mocker.patch("src.api.tasks.mdf_tasks.query_mdf_search")
    mock_query_search.return_value = httpx.Response(
        status_code=200, json=mock_response_body
    )

    mock_user = User(id=1, identity_id="3fa85f64-5717-4562-b3fc-2c963f66afa6")
    mock_get_user = mocker.patch("src.api.tasks.mdf_tasks._get_or_create_user")
    mock_get_user.return_value = mock_user

    mock_auth = Mock(spec=globus_sdk.ConfidentialAppAuthClient)

    await _add_dataset_from_completed_flow(
        mock_flow, mock_db_session, mock_settings, mock_auth
    )

    mock_db_session.delete.assert_called_once()
    deleted_object = mock_db_session.delete.call_args[0][0]
    assert deleted_object.versioned_source_id == versioned_source_id

    mock_db_session.add.assert_called_once()
    added_object = mock_db_session.add.call_args[0][0]
    assert added_object.versioned_source_id == versioned_source_id
    assert added_object.doi == doi

    mock_db_session.commit.assert_called_once()


def test_parse_doi_bad_query_resp():
    mock_response_body = {"bad": "response"}
    query_result = httpx.Response(status_code=404, json=mock_response_body)

    with pytest.raises(ValueError) as e:
        _parse_doi(query_result)
    assert (
        str(e.value)
        == "Unable to parse DOI, search query returned non 200 status code 404"
    )


def test_parse_doi_no_results():
    mock_response_body = {
        "total": 0,
        "count": 0,
        "gmeta": [],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    query_result = httpx.Response(status_code=200, json=mock_response_body)

    with pytest.raises(ValueError) as e:
        _parse_doi(query_result)
    assert (
        str(e.value)
        == "Unable to parse DOI, search result for pending MDF dataset returned no results."
    )


def test_parse_doi_many_results():
    mock_response_body = {
        "total": 2,
        "count": 2,
        "gmeta": [],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    query_result = httpx.Response(status_code=200, json=mock_response_body)

    with pytest.raises(ValueError) as e:
        _parse_doi(query_result)
    assert (
        str(e.value)
        == "Unable to parse DOI, search result for pending MDF dataset returned multiple results."
    )


def test_parse_doi_bad_format():
    mock_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": "a_source_id",
                "@version": "2019-08-27",
                "entries": [{"content": {"bad": "format"}}],
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    query_result = httpx.Response(status_code=200, json=mock_response_body)

    with pytest.raises(ValueError) as e:
        _parse_doi(query_result)
    assert (
        str(e.value)
        == "Unable to parse DOI, search result did not match expected format."
    )
