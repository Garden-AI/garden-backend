import asyncio
import functools

import httpx
from fastapi import HTTPException, exceptions, status
from globus_sdk import SearchClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.schemas.entrypoint import EntrypointPatchRequest
from src.api.schemas.garden import GardenPatchRequest
from src.api.schemas.modal.modal_function import ModalFunctionPatchRequest
from src.config import Settings
from src.models import Entrypoint, Garden, User, ModalFunction
from src.models._associations import gardens_entrypoints

logger = get_logger(__name__)


def assert_deletable_by_user(obj: Garden | Entrypoint, user: User) -> None:
    """Check that a given Garden or Entrypoint is safe to delete, i.e. has a draft DOI and is owned by the user.

    Raises:

        HTTPException: if obj is not owned by user or has a registered 'findable' DOI
    """
    if obj.owner.identity_id != user.identity_id:
        logger.info(
            f"Failed to delete or replace object {str(type(obj).__name__).lower()} (not owned by user)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete or replace (not owned by user {user.username})",
        )
    elif not obj.doi_is_draft:
        logger.info("Failed to delete or replace object (doi not draft)", doi=obj.doi)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete or replace {str(type(obj).__name__).lower()} (DOI {obj.doi} is registered as 'findable')",
        )
    return


def assert_editable_by_user(
    obj: Garden | Entrypoint | ModalFunction,
    patch_request: GardenPatchRequest | EntrypointPatchRequest | ModalFunctionPatchRequest,
    user: User,
) -> None:
    """Check that a given Garden or Entrypoint can be edited, i.e. is owned by the user and is not archived.

    Raises:
        HTTPException: If obj is not owned by user or is an archived resource (and resource is not being unarchived).
    """

    if obj.owner.identity_id != user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to edit {str(type(obj).__name__).lower()} (not owned by user {user.username})",
        )
    elif obj.is_archived and patch_request.is_archived is not False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to edit {str(type(obj).__name__).lower()} (DOI {obj.doi} is archived)",
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
        logger.info("Verified DOI is registered via doi.org", doi=doi)
        return True
    else:
        logger.info("DOI is not registered via doi.org", doi=doi)
        return False


async def get_gardens_for_entrypoint(
    entrypoint: Entrypoint, db: AsyncSession
) -> list[Garden] | None:
    garden_entrys = await db.scalars(
        select(Garden)
        .join(gardens_entrypoints, Garden.id == gardens_entrypoints.c.garden_id)
        .where(gardens_entrypoints.c.entrypoint_id == entrypoint.id)
    )
    return garden_entrys.all()


def deprecated(
    name="Endpoint",
    message: str = None,
    doc_url: str = "https://api.thegardens.ai/docs",
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


async def archive_on_datacite(doi: str, settings: Settings):
    """Hide a published doi on datacite.

    See: https://support.datacite.org/docs/updating-metadata-with-the-rest-api
    """
    body = {"data": {"type": "dois", "attributes": {"event": "hide"}}}

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{settings.DATACITE_ENDPOINT}/{doi}",
            headers={"Content-Type": "application/vnd.api+json"},
            auth=(settings.DATACITE_REPO_ID, settings.DATACITE_PASSWORD),
            json=body,
        )
        logger.info("Sent request to archive DOI on datacite", doi=doi)

    if response.status_code != 200:
        raise exceptions.HTTPException(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update DOI {doi} on Datacite: {response.json()}",
        )
