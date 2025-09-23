from datetime import datetime
from typing import AsyncGenerator

import globus_sdk
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import exc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.database import get_db_session
from src.auth.auth_state import AuthenticationState
from src.auth.globus_groups import add_user_to_group
from src.config import Settings, get_settings
from src.models.functions.modal.invocations import ModalInvocationLog
from src.models.user import User

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
) -> AsyncGenerator[User, None]:
    try:
        # First try to get the user
        user = await db.scalar(
            select(User).where(User.identity_id == auth.identity_id).limit(1)
        )

        created = False
        if user is None:
            try:
                # User doesn't exist, create them
                user = User(identity_id=auth.identity_id)
                db.add(user)
                await db.flush()
                created = True
            except exc.IntegrityError:
                # Another request created the user before us
                await db.rollback()
                user = await db.scalar(
                    select(User).where(User.identity_id == auth.identity_id).limit(1)
                )
                if user is None:
                    raise HTTPException(
                        status_code=500, detail="Failed to create or retrieve user"
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
    except Exception:
        log.exception("Error saving new authed_user")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # include username and id globally in any logs
    # emitted "downstream" in authed_user-dependants
    with structlog.contextvars.bound_contextvars(
        username=auth.username, user_identity_id=auth.identity_id
    ):
        yield user


async def under_modal_usage_limit(
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
) -> bool:
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate total estimated usage during the current month
    monthly_usage = await db.scalar(
        select(func.sum(ModalInvocationLog.estimated_usage)).where(
            ModalInvocationLog.user_id == user.id,
            ModalInvocationLog.date_invoked >= start_of_month,
        )
    )

    log.info(f"Calculated monthly usage: {monthly_usage}")

    if monthly_usage is None or monthly_usage < settings.MODAL_USAGE_LIMIT:
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is over Modal usage limit for the month.",
        )


def get_auth_client(
    settings: Settings = Depends(get_settings),
) -> globus_sdk.ConfidentialAppAuthClient:
    """Create an AuthClient for the service."""
    return globus_sdk.ConfidentialAppAuthClient(
        settings.API_CLIENT_ID, settings.API_CLIENT_SECRET
    )


def in_modal_publishers_group(
    auth: AuthenticationState = Depends(authenticated),
    auth_client: globus_sdk.ConfidentialAppAuthClient = Depends(get_auth_client),
    settings: Settings = Depends(get_settings),
) -> bool:
    try:
        dependent_tokens = auth_client.oauth2_get_dependent_tokens(auth.token)
        access_token = dependent_tokens.by_resource_server["groups.api.globus.org"][
            "access_token"
        ]
    except Exception as e:
        log.info("Could not recover dependent access token for groups.api.globus.org.")
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not determine group membership. Did you consent to share groups.api.globus.org when you logged in?",
        )

    # Create a Globus Group Client using the access token sent by the user
    authorizer = globus_sdk.AccessTokenAuthorizer(access_token)
    groups_client = globus_sdk.GroupsClient(authorizer=authorizer)

    # Collect the list of Globus Groups that the user is a member of
    try:
        user_groups = [group["id"] for group in groups_client.get_my_groups()]
    except Exception as e:
        log.info("Could not recover group memberships.")
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not determine group memberships.",
        )

    group_id = settings.MODAL_PUBLISHERS_GROUP_ID
    if group_id not in user_groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of the required group to publish Modal functions.",
        )
    return True


def is_super_user(
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Check if the authenticated user is a super user."""
    if str(user.identity_id) not in settings.SUPER_USERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a super user to perform this action",
        )
    return True
