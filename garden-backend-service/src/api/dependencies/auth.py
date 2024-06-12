import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_db_session
from src.auth.auth_state import AuthenticationState
from src.auth.globus_groups import in_garden_group, add_user_to_garden_group
from src.config import Settings, get_settings
from src.models.user import User


logger = logging.getLogger()


def _get_auth_token(
    authorization: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
):
    """Get the auth token from the Authorization header."""
    if not authorization:
        raise HTTPException(status_code=403, detail="Authorization header missing")
    return authorization.credentials


def _get_auth_state(
    token: str = Depends(_get_auth_token),
):
    """Get an AuthenticationState object from the token in the Authorization header."""
    return AuthenticationState(token)


def authenticated(
    auth_state: AuthenticationState = Depends(_get_auth_state),
) -> AuthenticationState:
    """Ensure the user is authenticated (i.e., has a valid token)"""
    auth_state.assert_is_authenticated()
    auth_state.assert_has_default_scope()
    return auth_state


async def authed_user(
    db: AsyncSession = Depends(get_db_session),
    auth: AuthenticationState = Depends(authenticated),
    settings: Settings = Depends(get_settings),
) -> User:

    user, created = await User.get_or_create(
        db,
        username=auth.username,
        identity_id=auth.identity_id,
        defaults={"group_added": False}
    )

    if created or not user.group_added:
        if not in_garden_group(auth, settings):
            await add_user_to_garden_group(auth, settings)

        user.group_added = True
        await db.commit()

    return user
