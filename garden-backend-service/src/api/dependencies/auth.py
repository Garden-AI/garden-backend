import globus_sdk
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.database import get_db_session
from src.auth.auth_state import AuthenticationState
from src.auth.globus_groups import add_user_to_group
from src.config import Settings, get_settings
from src.models.user import User
from structlog import get_logger

log = get_logger(__name__)


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
    try:
        user, created = await User.get_or_create(
            db,
            identity_id=auth.identity_id,
        )

        # Add the user to Garden Users Globus group if they are new
        if created:
            add_user_to_group(auth, settings)
            # populate fields we can get from the auth token
            user.name = auth.name
            user.email = auth.email
            user.username = auth.username
            await db.commit()
            log.info(
                "Added new user",
                username=auth.username,
                user_identity_id=auth.identity_id,
            )

        # include username and id automatically in logs
        # emitted from authed_user-dependent functions
        with structlog.contextvars.bound_contextvars(
            username=user.username, user_identity_id=user.identity_id
        ):
            yield user
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


def get_auth_client(
    settings: Settings = Depends(get_settings),
) -> globus_sdk.ConfidentialAppAuthClient:
    """Create an AuthClient for the service."""
    return globus_sdk.ConfidentialAppAuthClient(
        settings.API_CLIENT_ID, settings.API_CLIENT_SECRET
    )
