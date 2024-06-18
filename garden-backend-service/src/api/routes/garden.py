from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import assert_deletable_by_user
from src.api.schemas.garden import GardenCreateRequest, GardenMetadataResponse
from src.models import Entrypoint, Garden, User

router = APIRouter(prefix="/garden")
logger = getLogger(__name__)


@router.post("", response_model=GardenMetadataResponse)
async def add_garden(
    garden: GardenCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    # collect entrypoints by DOI
    stmt = select(Entrypoint).where(Entrypoint.doi.in_(garden.entrypoint_ids))
    result = await db.execute(stmt)
    entrypoints: list[Entrypoint] = result.scalars().all()

    if len(entrypoints) != len(garden.entrypoint_ids):
        missing_dois = [
            ep.doi for ep in entrypoints if ep.doi not in garden.entrypoint_ids
        ]
        raise HTTPException(
            status_code=404,
            detail=f"Failed to add garden. Could not find entrypoint(s) with DOIs: {missing_dois}",
        )
    # default owner is authed_user unless owner_identity_id is explicitly provided
    owner: User = user
    if garden.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=garden.owner_identity_id
        )
        if explicit_owner is not None:
            owner = explicit_owner
        else:
            logger.warning(
                f"No user found with Globus identity ID {garden.owner_identity_id}. "
                f"Assigning default ownership to {user.identity_id} ({user.username}). "
            )

    new_garden: Garden = Garden.from_dict(
        garden.model_dump(exclude={"entrypoint_ids", "owner_identity_id"})
    )
    new_garden.owner = owner
    new_garden.entrypoints = entrypoints

    db.add(new_garden)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garden with this DOI already exists",
        ) from e
    return new_garden


@router.get(
    "/{doi:path}",
    status_code=status.HTTP_200_OK,
    response_model=GardenMetadataResponse,
)
async def get_garden_by_doi(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
) -> GardenMetadataResponse:
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Garden not found with DOI {doi}",
        )
    return garden


@router.delete("/{doi:path}", status_code=status.HTTP_200_OK)
async def delete_garden(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is not None:
        assert_deletable_by_user(garden, user)
        await db.delete(garden)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Garden with DOI {doi}",
            ) from e
        return {"detail": f"Successfully deleted garden with DOI {doi}."}
    else:
        return {"detail": f"No garden found with DOI {doi}."}
