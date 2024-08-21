import logging
from typing import Any, Dict

import globus_sdk
import httpx
from fastapi import Depends
from src.auth.globus_auth import get_auth_client
from src.config import Settings

logger = logging.getLogger()


def get_globus_search_client(
    auth_client: globus_sdk.ConfidentialAppAuthClient = Depends(get_auth_client),
) -> globus_sdk.SearchClient:
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(
        auth_client, scopes=globus_sdk.SearchClient.scopes.all
    )
    search_client = globus_sdk.SearchClient(authorizer=cc_authorizer)
    return search_client


async def query_mdf_search(query: Dict[str, Any], settings: Settings) -> httpx.Response:
    """
    Runs globus search query against MDF search index.

    Args:
        query (Dict[str, Any]): GSearchQuery to run.
        settings (Settings): Application settings.

    Raises:
        globus_sdk.GlobusAPIError: when there is an issue communicating with Globus services
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://search.api.globus.org/v1/index/{settings.MDF_SEARCH_INDEX_UUID}/search",
            json=query,
            headers={"Content-Type": "application/json"},
        )
    return response
