import globus_sdk as glb

from src.config import Settings

from .auth_state import AuthenticationState
from .globus_auth import get_auth_client


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

    groups_manager = _create_service_groups_manager()
    groups_manager.add_member(settings.GARDEN_USERS_GROUP_ID, authed_user.identity_id)


def _create_service_groups_manager() -> glb.GroupsManager:
    """Return a globus_sdk GroupsManager acting as the backend service.

    Returns:
        globus_sdk.GroupsManager: Groups manager acting as the backend service.
    """
    gc = _create_service_groups_client()
    return glb.GroupsManager(client=gc)


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


def _create_groups_client_with_token(token: str) -> glb.GroupsClient:
    """Return a globus_sdk GroupsClient acting as the user that provides the token.

    Returns:
       globus_sdk.GroupsClient: Groups client using the provided token.
    """
    authorizer = glb.AccessTokenAuthorizer(token)
    return glb.GroupsClient(authorizer=authorizer)
