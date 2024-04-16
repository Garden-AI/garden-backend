import logging
from functools import lru_cache

import globus_sdk
from cachetools import TTLCache, cached
from fastapi import HTTPException
from src.config import get_settings

logger = logging.getLogger()


@cached(cache=TTLCache(maxsize=100, ttl=5 * 60))
def introspect_token(token: str, log: bool = True) -> globus_sdk.GlobusHTTPResponse:
    """Introspect a token and return the response data."""
    client = get_auth_client()
    auth_data = client.oauth2_token_introspect(
        token, include="identity_set,identity_set_detail"
    )

    if log:
        introspect_detail = getattr(auth_data, "data", auth_data)
        logger.debug(
            "auth_detail",
            extra={"log_type": "auth_detail", "auth_detail": introspect_detail},
        )

    if not auth_data.get("active", False):
        raise HTTPException(
            status_code=401,
            detail="Credentials not active",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_data


@lru_cache
def get_auth_client() -> globus_sdk.ConfidentialAppAuthClient:
    """Create an AuthClient for the service."""
    settings = get_settings()
    return globus_sdk.ConfidentialAppAuthClient(
        settings.API_CLIENT_ID, settings.API_CLIENT_SECRET
    )
