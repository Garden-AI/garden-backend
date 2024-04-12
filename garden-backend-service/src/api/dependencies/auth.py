import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.auth_state import AuthenticationState


logger = logging.getLogger("app")


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
    """Ensure the user is authenticated (i.e., has a valid token)
    """
    auth_state.assert_is_authenticated()
    auth_state.assert_has_default_scope()
    return auth_state
