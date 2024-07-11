from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.user import UserMetadataResponse, UserUpdateRequest
from src.models import User
from src.models._associations import users_saved_gardens

router = APIRouter(prefix="/users")


async def _get_saved_garden_dois(user: User, db: AsyncSession) -> list[str]:
    from src.models import Garden  # import here to avoid circular imports

    result = await db.execute(
        select(Garden.doi)
        .join(users_saved_gardens, Garden.id == users_saved_gardens.c.garden_id)
        .where(users_saved_gardens.c.user_id == user.id)
    )

    return [row[0] for row in result.all()]


@router.get("", status_code=status.HTTP_200_OK, response_model=UserMetadataResponse)
async def get_user_info(
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Return the user profile info for the current authed user."""
    saved_garden_dois = await _get_saved_garden_dois(authed_user, db)
    user_response = UserMetadataResponse(
        **authed_user.__dict__,
        saved_garden_dois=saved_garden_dois,
    )
    return user_response


@router.patch("", status_code=status.HTTP_200_OK, response_model=UserMetadataResponse)
async def update_user_info(
    user_update: UserUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    authed_user: User = Depends(authed_user),
):
    """Update the user profile info for the current authed user."""
    update_data: dict[str, Any] = user_update.dict(exclude_unset=True)

    # Setting the attributes automatically triggers an UPDATE on the next flush, or commit
    for key, value in update_data.items():
        setattr(authed_user, key, value)

    await db.commit()
    await db.refresh(authed_user)

    saved_garden_dois = await _get_saved_garden_dois(authed_user, db)
    user_response = UserMetadataResponse(
        **authed_user.__dict__,
        saved_garden_dois=saved_garden_dois,
    )
    return user_response
