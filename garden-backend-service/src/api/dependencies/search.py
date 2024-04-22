import logging

import globus_sdk
from fastapi import Depends
from src.auth.globus_auth import get_auth_client

logger = logging.getLogger()


def get_globus_search_client(
    auth_client: globus_sdk.ConfidentialAppAuthClient = Depends(get_auth_client),
) -> globus_sdk.SearchClient:
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(
        auth_client, scopes=globus_sdk.SearchClient.scopes.all
    )
    search_client = globus_sdk.SearchClient(authorizer=cc_authorizer)
    return search_client
