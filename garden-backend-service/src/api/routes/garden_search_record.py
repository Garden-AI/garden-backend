from fastapi import APIRouter, Depends, exceptions, status
from globus_sdk import SearchClient

from src.api.dependencies.auth import AuthenticationState, authenticated
from src.api.dependencies.search import get_globus_search_client
from src.api.routes._utils import deprecated, is_doi_registered, poll_globus_search_task
from src.api.schemas.search import DeleteSearchRecordRequest, PublishSearchRecordRequest
from src.config import Settings, get_settings

router = APIRouter(prefix="/garden-search-record")


@router.post("", status_code=status.HTTP_200_OK, deprecated=True)
@deprecated(
    name="/garden-search-record",
    message="Use /gardens instead or update garden-ai package to latest version.",
    doc_url="https://api.thegardens.ai/docs#/default/add_garden_gardens_post",
)
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
    return await poll_globus_search_task(task_id, search_client)


@router.delete("", status_code=status.HTTP_200_OK, deprecated=True)
@deprecated(
    name="/delete-search-record",
    message="Use /gardens instead or update garden-ai package to latest version.",
    doc_url="https://api.thegardens.ai/docs#/default/delete_garden_gardens__doi__delete",
)
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
    return await poll_globus_search_task(task_id, search_client)
