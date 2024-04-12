import typing as t
import uuid

import globus_sdk
from fastapi import HTTPException
from src.auth.globus_auth import introspect_token
from src.config import settings


class AuthenticationState:
    """
    This is a dedicated object for handling authentication.

    It takes in a Globus Auth token and resolve it to a user and various data about that
    user. It is the "auth_state" object for the application within the context of a
    request, showing "who" is calling the application (e.g. identity_id) and some
    information about "how" the call is being made (e.g. scopes).

    For the most part, this should not handle authorization checks, to maintain
    separation of concerns.

    NB: This class was lifted almost verbatim from funcx web service's auth
    code. It seemed sane enough, plus doing so will hopefully streamline
    the Developer Experience of plagiarizing other pieces of their code.
    """

    def __init__(
        self, token: t.Optional[str], *, assert_default_scope: bool = True
    ) -> None:
        self.garden_default_scope: str = settings.GARDEN_DEFAULT_SCOPE
        self.token = token

        self.introspect_data: t.Optional[globus_sdk.GlobusHTTPResponse] = None
        self.identity_id: t.Optional[uuid.UUID] = None
        self.username: t.Optional[str] = None
        self.scopes: t.Set[str] = set()

        if token:
            self._handle_token()

    def _handle_token(self) -> None:
        """Given a token, flesh out the AuthenticationState."""
        self.introspect_data = introspect_token(t.cast(str, self.token))
        self.username = self.introspect_data["username"]
        self.identity_id = (
            uuid.UUID(self.introspect_data["sub"])
            if self.introspect_data["sub"]
            else None
        )
        self.scopes = set(self.introspect_data["scope"].split(" "))

    @property
    def is_authenticated(self):
        return self.identity_id is not None

    def assert_is_authenticated(self):
        """
        This tests that is_authenticated=True, and raises an Unauthorized error
        (401) if it is not.
        """
        if not self.is_authenticated:
            raise HTTPException(
                status_code=401, detail="method requires token authenticated access"
            )

    def assert_has_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=403, detail="Missing Scopes")

    def assert_has_default_scope(self) -> None:
        self.assert_has_scope(self.garden_default_scope)
