from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._tasks import (
    create_or_update_on_search_index,
    delete_from_search_index,
)
from src.api.routes._utils import assert_deletable_by_user, is_doi_registered
from src.api.schemas.garden import GardenCreateRequest, GardenMetadataResponse
from src.config import Settings, get_settings
from src.models import Entrypoint, Garden, User

router = APIRouter(prefix="/gardens")
logger = getLogger(__name__)


@router.post("", response_model=GardenMetadataResponse)
async def add_garden(
    garden: GardenCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    new_garden = await _create_new_garden(garden, db, user)
    if settings.SYNC_SEARCH_INDEX:
        logger.info(msg=f"Sending garden {new_garden.doi} to search index")
        background_tasks.add_task(
            create_or_update_on_search_index, new_garden, settings
        )
    return new_garden


@router.get("", response_model=list[GardenMetadataResponse])
async def search_gardens(
    doi: Annotated[list[str] | None, Query()] = None,
    doi_is_draft: Annotated[bool | None, Query()] = None,
    owner_uuid: Annotated[UUID | None, Query()] = None,
    authors: Annotated[list[str] | None, Query()] = None,
    contributors: Annotated[list[str] | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    year: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(max_value=100)] = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch multiple gardens according to query parameters"""
    stmt = select(Garden)

    if doi is not None:
        stmt = stmt.where(Garden.doi.in_(doi))

    if doi_is_draft is not None:
        stmt = stmt.where(Garden.doi_is_draft == doi_is_draft)

    if owner_uuid is not None:
        stmt = stmt.join(Garden.user).where(User.identity_id == owner_uuid)

    if authors is not None:
        stmt = stmt.where(Garden.authors.overlap(array(authors)))

    if contributors is not None:
        stmt = stmt.where(Garden.contributors.overlap(array(contributors)))

    if tags is not None:
        stmt = stmt.where(Garden.tags.overlap(array(tags)))

    if year is not None:
        stmt = stmt.where(Garden.year == year)

    result = await db.scalars(stmt.limit(limit))
    return result.all()


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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is not None:
        assert_deletable_by_user(garden, user)
        await db.delete(garden)
        try:
            await db.commit()
            if settings.SYNC_SEARCH_INDEX:
                logger.info(msg=f"Deleting garden {garden.doi} from search index")
                background_tasks.add_task(delete_from_search_index, garden, settings)
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Garden with DOI {doi}",
            ) from e
        return {"detail": f"Successfully deleted garden with DOI {doi}."}
    else:
        return {"detail": f"No garden found with DOI {doi}."}


@router.put("/{doi:path}", response_model=GardenMetadataResponse)
async def create_or_replace_garden(
    doi: str,
    background_tasks: BackgroundTasks,
    garden_data: GardenCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    existing_garden: Garden | None = await Garden.get(db, doi=doi)
    if existing_garden is None:
        new_garden = await _create_new_garden(garden_data, db, user)
        if settings.SYNC_SEARCH_INDEX:
            logger.log(msg=f"Sending garden {new_garden.doi} to search index")
            background_tasks.add_task(
                create_or_update_on_search_index, new_garden, settings
            )
        return new_garden

    # check draft status with the real world (doi.org)
    if garden_data.doi_is_draft is None:
        registered = await is_doi_registered(garden_data.doi)
        garden_data.doi_is_draft = not registered

    assert_deletable_by_user(existing_garden, user)
    # update ownership if specified
    if garden_data.owner_identity_id is not None:
        new_owner: User | None = await User.get(
            db, identity_id=garden_data.owner_identity_id
        )
        existing_garden.owner = new_owner or user

    # update related entrypoints
    new_entrypoints = await _collect_entrypoints(garden_data.entrypoint_ids, db)
    existing_garden.entrypoints = new_entrypoints

    # naive update with remaining values from payload
    for key, value in garden_data.model_dump(
        exclude={"owner_identity_id", "entrypoint_ids"}
    ).items():
        setattr(existing_garden, key, value)
    try:
        await db.commit()
        if settings.SYNC_SEARCH_INDEX:
            logger.info(msg=f"Updating garden {existing_garden.doi} on search index")
            background_tasks.add_task(
                create_or_update_on_search_index, existing_garden, settings
            )
    except IntegrityError as e:
        logger.error(str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error occurred: {str(e)}",
        ) from e

    return existing_garden


async def _collect_entrypoints(dois: list[str], db: AsyncSession) -> list[Entrypoint]:
    stmt = select(Entrypoint).where(Entrypoint.doi.in_(dois))
    result = await db.execute(stmt)
    entrypoints: list[Entrypoint] = result.scalars().all()

    if len(entrypoints) != len(dois):
        missing_dois = [ep.doi for ep in entrypoints if ep.doi not in dois]
        raise HTTPException(
            status_code=404,
            detail=f"Could not find entrypoint(s) with DOIs: {missing_dois}",
        )
    return entrypoints


async def _create_new_garden(
    garden_data: GardenCreateRequest,
    db: AsyncSession,
    user: User,
):
    # if not specified, check draft status with the real world (doi.org)
    if garden_data.doi_is_draft is None:
        registered = await is_doi_registered(garden_data.doi)
        garden_data.doi_is_draft = not registered

    # collect entrypoints by DOI
    entrypoints = await _collect_entrypoints(garden_data.entrypoint_ids, db)

    # default owner is authed_user unless owner_identity_id is explicitly provided
    owner: User = user
    if garden_data.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=garden_data.owner_identity_id
        )
        if explicit_owner is not None:
            owner = explicit_owner
        else:
            logger.warning(
                f"No user found with Globus identity ID {garden_data.owner_identity_id}. "
                f"Assigning default ownership to {user.identity_id} ({user.username}). "
            )

    new_garden: Garden = Garden.from_dict(
        garden_data.model_dump(exclude={"entrypoint_ids", "owner_identity_id"})
    )
    new_garden.owner = owner
    new_garden.entrypoints = entrypoints

    db.add(new_garden)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Could not create new garden: {e}",
        ) from e
    return new_garden
