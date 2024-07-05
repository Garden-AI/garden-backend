from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.user import UserMetadataResponse, UserUpdateRequest
from src.models import User

router = APIRouter(prefix="/users")


@router.get("", status_code=status.HTTP_200_OK, response_model=UserMetadataResponse)
async def get_user_info(
    authed_user: User = Depends(authed_user),
):
    """Return the user profile info for the current authed user."""
    return authed_user


@router.patch("", status_code=status.HTTP_200_OK, response_model=UserMetadataResponse)
async def update_user_info(
    user_update: UserUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    authed_user: User = Depends(authed_user),
):
    """Update the user profile info for the current authed user."""
    update_data: Dict[str, Any] = user_update.dict(exclude_unset=True)

    # Setting the attributes automatically triggers an UPDATE on the next flush, or commit
    for key, value in update_data.items():
        setattr(authed_user, key, value)

    await db.commit()
    await db.refresh(authed_user)

    return authed_user
