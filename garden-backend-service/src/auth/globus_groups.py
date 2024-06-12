import logging

import globus_sdk as glb

from src.models import User
from src.config import Settings

from .auth_state import AuthenticationState
from .globus_auth import get_auth_client

logger = logging.getLogger(__name__)


def add_user_to_garden_group(
    authed_user: AuthenticationState,
    settings: Settings,
) -> None:
    """Add authed_user as a member of Garden Users Globus group specified in the settings.

    If the user is already in the group this function does nothing.
    """
    try:
        if not in_garden_group(authed_user):
            gm = _get_service_groups_manager()
            gm.add_member(settings.GARDEN_USERS_GROUP_ID, authed_user.identity_id)
    except glb.GlobusAPIError as e:
        logger.error(f"Error adding user to Garden Users Group: {e}")
        raise e

def in_garden_group(
    authed_user: AuthenticationState,
    settings: Settings,
) -> bool:
    """Return true if authed_user is a member of the Garden Users Globus group specified in the settings."""
    try:
        gc = _get_groups_client_for_token(authed_user.token)
        groups = _get_groups(gc)
        return any(group.get("id") == settings.GARDEN_USERS_GROUP_ID for group in groups)
    except glb.GlobusAPIError as e:
        logger.error(f"Error getting user Globus groups: {e}")
        raise e


def _get_groups(client: glb.GroupsClient) -> list[dict]:
    """Return a list of group data objects for the given client."""
    return [group for group in client.get_my_groups()]


def _get_service_groups_client() -> glb.GroupsClient:
    """Return a globus_sdk GroupsClient acting as the backend service."""
    gc = get_auth_client()
    tokens = gc.oauth2_client_credentials_tokens(
        requested_scopes="urn:globus:auth:scope:groups.api.globus.org:all",
    )
    auth_data = tokens.by_resource_server.get("groups.api.globus.org")
    token = auth_data.get("access_token")
    return _get_groups_client_for_token(token)


def _get_service_groups_manager() -> glb.GroupsManager:
    """Return a globus_sdk GroupsManager acting as the backend service."""
    gc = _get_servoce_groups_client()
    return glb.GroupsManager(client=gc)

def _get_groups_client_for_token(token: str) -> glb.GroupsClient:
    """Return a globus_sdk GroupsClient acting as the user that provides the token."""
    authorizer = glb.AccessTokenAuthorizer(token)
    return glb.GroupsClient(authorizer=authorizer)


# #TODO DELETE ME BEFORE MAKING A PR!
# def request_to_join():
#     """One time function to have the backend service request to join the Garden Users group"""
#     c = get_auth_client()
#     settings = get_settings()
#     gc = _get_groups_client()
#     gm = globus_sdk.GroupsManager(client=gc)
#     gm.request_join(settings.GARDEN_USERS_GROUP_ID, settings.API_CLIENT_ID)
