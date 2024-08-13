from unittest.mock import AsyncMock

import httpx
import pytest
from src.models import Dataset, User


@pytest.mark.asyncio
async def test_search_with_db_entry(
    client,
    mock_db_session,
    mock_settings,
    mocker,
):
    versioned_source_id = "a_versioned_source_id"
    doi = "a_doi"
    owner_identity_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    mock_request_body = {
        "q": f"{versioned_source_id}",
        "limit": 1,
        "advanced": True,
        "filters": [
            {
                "type": "match_all",
                "field_name": "mdf.resource_type",
                "values": ["dataset"],
            }
        ],
    }
    mock_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": f"{versioned_source_id}",
                "@version": "2019-08-27",
                "entries": [],
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    expected_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": f"{versioned_source_id}",
                "@version": "2019-08-27",
                "entries": [],
                "accelerate_metadata": {
                    "owner_identity_id": f"{owner_identity_id}",
                    "connected_entrypoints": [],
                    "previous_versions": None,
                },
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }

    mock_query_search = mocker.patch("src.api.routes.mdf.search._query_search")
    mock_query_search.return_value = httpx.Response(
        status_code=200, json=mock_response_body
    )

    mock_user = User(id=1, identity_id=owner_identity_id)
    mock_dataset = Dataset(
        id=1, versioned_source_id=versioned_source_id, doi=doi, owner=mock_user
    )
    mock_dataset_get = mocker.patch("src.models.Dataset.get", new_callable=AsyncMock)
    mock_dataset_get.return_value = mock_dataset

    response = await client.post("/mdf/search", json=mock_request_body)

    assert response.status_code == 200
    assert response.json() == expected_response_body


@pytest.mark.asyncio
async def test_search_with_no_db_entry(
    client,
    mock_db_session,
    mock_settings,
    mocker,
):
    versioned_source_id = "another_versioned_source_id"
    mock_request_body = {
        "q": f"{versioned_source_id}",
        "limit": 1,
        "advanced": True,
        "filters": [
            {
                "type": "match_all",
                "field_name": "mdf.resource_type",
                "values": ["dataset"],
            }
        ],
    }
    mock_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": f"{versioned_source_id}",
                "@version": "2019-08-27",
                "entries": [],
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }
    expected_response_body = {
        "total": 1,
        "count": 1,
        "gmeta": [
            {
                "subject": f"{versioned_source_id}",
                "@version": "2019-08-27",
                "entries": [],
                "accelerate_metadata": None,
            }
        ],
        "has_next_page": False,
        "offset": 0,
        "facet_results": None,
    }

    mock_query_search = mocker.patch("src.api.routes.mdf.search._query_search")
    mock_query_search.return_value = httpx.Response(
        status_code=200, json=mock_response_body
    )

    response = await client.post("/mdf/search", json=mock_request_body)

    assert response.status_code == 200
    assert response.json() == expected_response_body
