import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.models.user import User
from src.api.dependencies.database import get_db_session
from src.auth.auth_state import AuthenticationState
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> User:
    return await User.get_or_create(
        db, username=auth.username, identity_id=auth.identity_id
    )
