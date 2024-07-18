from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import and_
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.user import UserMetadataResponse, UserUpdateRequest
from src.models import Garden, User
from src.models._associations import users_saved_gardens

router = APIRouter(prefix="/users")


async def _get_saved_garden_dois(user: User, db: AsyncSession) -> list[str]:
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


@router.get("/gardens/saved")
async def get_saved_garden_dois(
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[str]:
    return await _get_saved_garden_dois(authed_user, db)


@router.patch("/gardens/saved/{doi:path}")
async def save_garden(
    doi: str,
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[str]:
    user: User = await User.get(db, identity_id=authed_user.identity_id)
    garden: Garden | None = await Garden.get(db, doi=doi)

    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No garden with doi {doi} found.",
        )

    try:
        stmt = insert(users_saved_gardens).values(user_id=user.id, garden_id=garden.id)
        await db.execute(stmt)
        await db.commit()
        return await _get_saved_garden_dois(authed_user, db)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has already saved this garden.",
        ) from e


@router.delete("/gardens/saved/{doi:path}")
async def remove_saved_garden(
    doi: str,
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[str]:
    """Remove a garden from the authed users list of saved gardens by doi."""
    user: User = await User.get(db, identity_id=authed_user.identity_id)
    garden: Garden | None = await Garden.get(db, doi=doi)

    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No garden with doi {doi} found.",
        )

    try:
        stmt = delete(users_saved_gardens).where(
            and_(
                users_saved_gardens.c.user_id == user.id,
                users_saved_gardens.c.garden_id == garden.id,
            )
        )
        await db.execute(stmt)
        await db.commit()
        return await _get_saved_garden_dois(authed_user, db)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to remove saved garden with doi {doi} due to integrity contraints",
        ) from e
