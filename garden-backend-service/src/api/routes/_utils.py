from fastapi import HTTPException, status
from src.models import Entrypoint, Garden, User


def assert_deletable_by_user(obj: Garden | Entrypoint, user: User):
    """Check that a given Garden or Entrypoint is safe to delete, i.e. has a draft DOI and is owned by the user.

    Raises:

        HTTPException: if obj is not owned by user or has a registered 'findable' DOI
    """
    if obj.owner.identity_id != user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete {type(obj)} (not owned by user {user.username})",
        )
    elif not obj.doi_is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete {type(obj)} (DOI {obj.doi} is registered as 'findable')",
        )
    return
