import logging

import globus_sdk
from fastapi import Depends
from src.auth.globus_auth import get_auth_client

logger = logging.getLogger()


def get_globus_flows_client(
    auth_client: globus_sdk.ConfidentialAppAuthClient = Depends(get_auth_client),
) -> globus_sdk.FlowsClient:
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(
        auth_client,
        scopes=[
            globus_sdk.FlowsClient.scopes.run_status,
        ],
    )
    flows_client = globus_sdk.FlowsClient(authorizer=cc_authorizer)
    return flows_client
