import logging

import globus_sdk as glb

from src.models import User
from src.config import Settings

from .auth_state import AuthenticationState
from .globus_auth import get_auth_client

logger = logging.getLogger(__name__)


def add_user_to_group(
    authed_user: AuthenticationState,
    settings: Settings,
) -> None:
    """Add authed_user as a member of Garden Users Globus group specified in the settings.

    If the user is already in the group this function does nothing.

    Args:
        authed_user (AuthenticationState): The authenticated user.
        settings (Settings): Application settings.

    Raises:
        globus_sdk.GlobusAPIError: when there is an issue communicating with Globus services
    """
    try:
        if not is_user_in_group(authed_user, settings):
            groups_manager = _create_service_groups_manager()
            groups_manager.add_member(settings.GARDEN_USERS_GROUP_ID, authed_user.identity_id)
    except glb.GlobusAPIError as e:
        logger.error(f"Error adding user to Garden Users Group: {e}")
        raise e


def is_user_in_group(
    authed_user: AuthenticationState,
    settings: Settings,
) -> bool:
    """Return true if authed_user is a member of the Garden Users Globus group specified in the settings.

    Args:
        authed_user (AuthenticationState): The authenticated user
        settings (Settings): Application Settings

    Raises:
        globus_sdk.GlobusAPIError: When there is an issue communicating with Globus services
    """
    try:
        gc = _create_groups_client_with_token(authed_user.token)
        groups = _fetch_user_groups(gc)
        return any(group.get("id") == settings.GARDEN_USERS_GROUP_ID for group in groups)
    except glb.GlobusAPIError as e:
        logger.error(f"Error getting user Globus groups: {e}")
        raise e


def _fetch_user_groups(client: glb.GroupsClient) -> list[dict]:
    """Return a list of group data objects for the given client.

    Args:
        client (globus_sdk.GroupsClient): A groups client.


    Returns:
        list[dict]: List of group data objects.
            See https://globus-sdk-python.readthedocs.io/en/stable/services/groups.html#globus_sdk.GroupsClient.get_my_groups
    """
    return [group for group in client.get_my_groups()]


def _create_service_groups_client() -> glb.GroupsClient:
    """Return a globus_sdk GroupsClient acting as the backend service.

    Returns:
        globus_sdk.GroupsClient: Groups client acting as the backend service.
    """
    gc = get_auth_client()
    tokens = gc.oauth2_client_credentials_tokens(
        requested_scopes="urn:globus:auth:scope:groups.api.globus.org:all",
    )
    auth_data = tokens.by_resource_server.get("groups.api.globus.org")
    token = auth_data.get("access_token")
    return _create_groups_client_with_token(token)


def _create_service_groups_manager() -> glb.GroupsManager:
    """Return a globus_sdk GroupsManager acting as the backend service.

    Returns:
        globus_sdk.GroupsManager: Groups manager acting as the backend service.
    """
    gc = _create_service_groups_client()
    return glb.GroupsManager(client=gc)


def _create_groups_client_with_token(token: str) -> glb.GroupsClient:
    """Return a globus_sdk GroupsClient acting as the user that provides the token.

    Returns:
       globus_sdk.GroupsClient: Groups client using the provided token.
    """
    authorizer = glb.AccessTokenAuthorizer(token)
    return glb.GroupsClient(authorizer=authorizer)


#TODO DELETE ME BEFORE MAKING A PR!
def request_to_join():
    """One time function to have the backend service request to join the Garden Users group"""
    c = get_auth_client()
    settings = get_settings()
    gc = _fetch_user_groups_client()
    gm = globus_sdk.GroupsManager(client=gc)
    gm.request_join(settings.GARDEN_USERS_GROUP_ID, settings.API_CLIENT_ID)
