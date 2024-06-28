import httpx
from fastapi import HTTPException, status
from src.models import Entrypoint, Garden, User


def assert_deletable_by_user(obj: Garden | Entrypoint, user: User) -> None:
    """Check that a given Garden or Entrypoint is safe to delete, i.e. has a draft DOI and is owned by the user.

    Raises:

        HTTPException: if obj is not owned by user or has a registered 'findable' DOI
    """
    if obj.owner.identity_id != user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete {str(type(obj).__name__).lower()} (not owned by user {user.username})",
        )
    elif not obj.doi_is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete {str(type(obj).__name__).lower()} (DOI {obj.doi} is registered as 'findable')",
        )
    return


async def is_doi_registered(doi: str) -> bool:
    """
    Check if a DOI is registered in the real world by querying the doi.org resolver.

    Parameters:
    doi (str): The DOI to check.

    Returns:
    bool: True if the DOI resolves successfully, False otherwise.
    """
    url = f"https://doi.org/{doi}"

    headers = {"Accept": "application/vnd.citationstyles.csl+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        response = await client.get(url, follow_redirects=False)

    # Check if the response status code is a redirect (300-399), indicating the DOI is registered
    if 300 <= response.status_code < 400:
        return True
    else:
        return False
