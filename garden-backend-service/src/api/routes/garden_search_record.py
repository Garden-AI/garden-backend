import asyncio

from fastapi import APIRouter, Depends, exceptions, status
from globus_sdk import SearchClient
from src.api.dependencies.auth import AuthenticationState, authenticated
from src.api.dependencies.search import get_globus_search_client
from src.api.schemas.search import DeleteSearchRecordRequest, PublishSearchRecordRequest
from src.config import Settings, get_settings
from src.api.routes._utils import is_doi_registered

router = APIRouter(prefix="/garden-search-record")


@router.post("", status_code=status.HTTP_200_OK)
async def publish_search_record(
    garden_meta: PublishSearchRecordRequest,
    settings: Settings = Depends(get_settings),
    search_client: SearchClient = Depends(get_globus_search_client),
    _auth: AuthenticationState = Depends(authenticated),
):
    gmeta_ingest = {
        "subject": garden_meta.doi,
        "visible_to": ["public"],
        "content": garden_meta.dict(),
    }
    search_create_result = search_client.create_entry(
        settings.GLOBUS_SEARCH_INDEX_ID, gmeta_ingest
    )
    task_id = search_create_result["task_id"]
    return await _poll_globus_search_task(task_id, search_client)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_search_record(
    body: DeleteSearchRecordRequest,
    settings: Settings = Depends(get_settings),
    search_client: SearchClient = Depends(get_globus_search_client),
    _auth: AuthenticationState = Depends(authenticated),
):
    registered = await is_doi_registered(body.doi)
    if registered:
        raise exceptions.HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"Error: DOI {body.doi} has been publicly registered and cannot be deleted.",
        )
    search_delete_result = search_client.delete_entry(
        settings.GLOBUS_SEARCH_INDEX_ID, body.doi
    )
    task_id = search_delete_result["task_id"]
    return await _poll_globus_search_task(task_id, search_client)


async def _poll_globus_search_task(
    task_id, search_client: SearchClient, max_intervals=25
):
    task_result = search_client.get_task(task_id)
    while task_result["state"] not in {"FAILED", "SUCCESS"}:
        if max_intervals == 0:
            raise exceptions.HTTPException(
                status.HTTP_408_REQUEST_TIMEOUT,
                detail=(
                    "Server timed out waiting for globus search task to finish. "
                    f"You can manually check its progress with the task id: {task_id}"
                ),
            )
        await asyncio.sleep(0.2)
        max_intervals -= 1
        task_result = search_client.get_task(task_id)

    if task_result["state"] == "SUCCESS":
        return {}
    else:
        raise exceptions.HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=task_result.text
        )
