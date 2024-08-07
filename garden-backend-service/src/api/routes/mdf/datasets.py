from logging import getLogger
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import Json
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.database import get_db_session
from src.config import Settings, get_settings
from src.models import Dataset

logger = getLogger(__name__)

router = APIRouter(prefix="/mdf")


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
)
async def search_datasets(
    request: Request,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """
    Accepts Globus GSearchRequest in request body.
    Acts as an intermediary for querying MDF's globus search index and then augments the query results with
    any accelerate metadata stored in the garden backend (connected_entrypoints, owner_identity_id, etc..)

    Does not require user auth since MDF search index also does not require auth.
    Does not support globus search scroll queries.
    """

    query = await request.json()

    response = await _query_search(query, settings)
    if response.status_code == 200:
        response_json = response.json()
        gmeta = response_json.get("gmeta", [])

        # For each SI record, grab matching dataset from 'mdf_datasets' table and add accelerate_metadata to query result
        for i in range(len(gmeta)):
            record = gmeta[i]
            versioned_source_id = record.get("subject", None)

            if versioned_source_id:
                dataset: Dataset | None = await Dataset.get(
                    db, versioned_source_id=versioned_source_id
                )
                if dataset:
                    entries = record.get("entries", [])
                    if (
                        len(entries) == 1
                    ):  # SI is formatted so entries should always be length 1
                        gmeta[i]["entries"][0][
                            "accelerate_metadata"
                        ] = dataset.get_accelerate_metadata()

        response_json["gmeta"] = gmeta
        return JSONResponse(content=response_json, status_code=status.HTTP_200_OK)
    else:
        # Pass on search error if response code is not 200
        logger.warning(
            msg=f"MDF search query returned status code {response.status_code}"
        )
        raise HTTPException(status_code=response.status_code, detail=response.json())


async def _query_search(query: Json[Any], settings: Settings) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.MDF_SEARCH_INDEX,
            json=query,
            headers={"Content-Type": "application/json"},
        )
    return response
