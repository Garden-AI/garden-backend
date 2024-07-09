import asyncio
import functools

import httpx
from fastapi import HTTPException, exceptions, status
from globus_sdk import SearchClient
from src.api.dependencies.search import get_globus_search_client
from src.auth.globus_auth import get_auth_client
from src.config import get_settings
from src.models import Entrypoint, Garden, User


def assert_deletable_by_user(obj: Garden | Entrypoint, user: User) -> None:
    """Check that a given Garden or Entrypoint is safe to delete, i.e. has a draft DOI and is owned by the user.

    Raises:

        HTTPException: if obj is not owned by user or has a registered 'findable' DOI
    """
    if obj.owner.identity_id != user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete or replace {str(type(obj).__name__).lower()} (not owned by user {user.username})",
        )
    elif not obj.doi_is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete or replace {str(type(obj).__name__).lower()} (DOI {obj.doi} is registered as 'findable')",
        )
    return


async def is_doi_registered(doi: str) -> bool:
    """
    Check if a DOI is registered in the real world by querying the doi.org resolver.

    Parameters:
    doi (str): The DOI to check.

    Returns:
    bool: True if the DOI resolves successfully, False otherwise.
    """
    url = f"https://doi.org/{doi}"

    headers = {"Accept": "application/vnd.citationstyles.csl+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        response = await client.get(url, follow_redirects=False)

    # Check if the response status code is a redirect (300-399), indicating the DOI is registered
    if 300 <= response.status_code < 400:
        return True
    else:
        return False


def deprecated(
    name="Endpoint",
    message: str = None,
    doc_url: str = "https://api-dev.thegardens.ai/docs",
):
    """Mark an endpoint as deprecated.

    Causes the endpoint to return a 410 response with optional message and docs link.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=f"{name} is deprecated. {message if message is not None else ''} See: {doc_url}",
            )

        return wrapper

    return decorator


async def poll_globus_search_task(
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


async def delete_from_search_index(garden_data):
    settings = get_settings()
    if settings.SYNC_SEARCH_INDEX:
        client = get_globus_search_client(get_auth_client())
        delete_result = client.delete_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_data.doi,
        )
        task_id = delete_result["task_id"]
        return await poll_globus_search_task(task_id, client)


async def create_or_update_on_search_index(garden_data):
    settings = get_settings()
    if settings.SYNC_SEARCH_INDEX:
        client = get_globus_search_client(get_auth_client())
        create_result = client.create_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_data.doi,
        )
        task_id = create_result["task_id"]
        return await poll_globus_search_task(task_id, client)
