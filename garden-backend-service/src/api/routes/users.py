from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.garden import GardenMetadataResponse
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


@router.get("/{user_uuid}/saved/gardens", response_model=list[GardenMetadataResponse])
async def get_saved_gardens(
    user_uuid: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[GardenMetadataResponse]:
    """Fetch the users list of saved gardens."""
    user: User | None = await User.get(db, identity_id=user_uuid)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with uuid {user_uuid} found.",
        )

    # We need to explicitly load the saved_gardens field
    await db.refresh(user, ["saved_gardens"])
    return [
        GardenMetadataResponse.model_validate(garden) for garden in user.saved_gardens
    ]


@router.put(
    "/{user_uuid}/saved/gardens/{doi:path}", response_model=list[GardenMetadataResponse]
)
async def save_garden(
    user_uuid: UUID,
    doi: str,
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[GardenMetadataResponse]:
    """Add a garden to the user's list of saved gardens by doi."""
    user: User | None = await User.get(db, identity_id=user_uuid)
    garden: Garden | None = await Garden.get(db, doi=doi)

    if user_uuid != authed_user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Not authorized to save a garden for user {user_uuid}.",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with user_uuid {user_uuid} found.",
        )

    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No garden with doi {doi} found.",
        )

    await db.refresh(user, ["saved_gardens"])
    if garden not in user.saved_gardens:
        user.saved_gardens.append(garden)

    try:
        await db.commit()
        return user.saved_gardens
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already saved this garden.",
        ) from e


@router.delete("/{user_uuid}/saved/gardens/{doi:path}")
async def remove_saved_garden(
    user_uuid: UUID,
    doi: str,
    authed_user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[GardenMetadataResponse]:
    """Remove a garden from the user's list of saved gardens by doi."""

    if user_uuid != authed_user.identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Not authorized to remove a saved garden for user {user_uuid}.",
        )

    user: User | None = await User.get(db, identity_id=user_uuid)
    garden: Garden | None = await Garden.get(db, doi=doi)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with user_uuid {user_uuid} found.",
        )

    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No garden with doi {doi} found.",
        )

    await db.refresh(user, ["saved_gardens"])
    if garden in user.saved_gardens:
        user.saved_gardens.remove(garden)

    try:
        await db.commit()
        return [
            GardenMetadataResponse.model_validate(garden)
            for garden in user.saved_gardens
        ]
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unable to remove saved garden with doi {doi} due to integrity contraints",
        ) from e
