from logging import getLogger
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._tasks import create_or_update_on_search_index
from src.api.routes._utils import assert_deletable_by_user, get_gardens_for_entrypoint
from src.api.schemas.entrypoint import (
    EntrypointCreateRequest,
    EntrypointMetadataResponse,
)
from src.config import Settings, get_settings
from src.models import Entrypoint, Garden, User

logger = getLogger(__name__)

router = APIRouter(prefix="/entrypoints")


@router.post("", response_model=EntrypointMetadataResponse)
async def add_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    return await _create_new_entrypoint(entrypoint, db, user)


# note: the ':path' is a starlette converter option to include '/' characters
# from the rest of the path. This also handles encoded '%2F' slashes correctly
# see also: https://www.starlette.io/routing/#path-parameters
@router.get(
    "/{doi:path}",
    status_code=status.HTTP_200_OK,
    response_model=EntrypointMetadataResponse,
)
async def get_entrypoint_by_doi(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
) -> EntrypointMetadataResponse:
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)
    if entrypoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entrypoint not found with DOI {doi}",
        )
    return entrypoint


@router.get("", status_code=status.HTTP_200_OK)
async def get_entrypoints(
    db: AsyncSession = Depends(get_db_session),
    *,
    dois: list[str] | None = Query(None),
    tags: list[str] | None = Query(None),
    authors: list[str] | None = Query(None),
    owner: UUID | None = Query(None),
    draft: bool | None = Query(None),
    year: str | None = Query(None),
    limit: int = Query(50),
) -> list[EntrypointMetadataResponse]:
    """Fetch multiple entrypoints according to query parameters."""
    stmt = select(Entrypoint)
    if dois:
        stmt = stmt.where(Entrypoint.doi.in_(dois))
    if tags:
        stmt = stmt.where(Entrypoint.tags.overlap(array(tags)))
    if authors:
        stmt = stmt.where(Entrypoint.authors.overlap(array(authors)))
    if owner:
        stmt = stmt.where(Entrypoint.owner.identity_id == owner)
    if draft is not None:
        stmt = stmt.where(Entrypoint.doi_is_draft == draft)
    if year:
        stmt = stmt.where(Entrypoint.year == year)

    result = await db.scalars(stmt.limit(limit))
    return result.all()


@router.delete("/{doi:path}", status_code=status.HTTP_200_OK)
async def delete_entrypoint(
    doi: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)

    if entrypoint is not None:
        assert_deletable_by_user(entrypoint, user)
        gardens: list[Garden] | None = await get_gardens_for_entrypoint(entrypoint, db)
        await db.delete(entrypoint)
        try:
            await db.commit()
            if gardens:
                for garden in gardens:
                    db.refresh(garden)
                    if settings.SYNC_SEARCH_INDEX:
                        # just update the gardens, we don't want to delete a garden just because we deleted an entrypoint
                        logger.info(msg=f"Updating garden {garden.doi} on search index")
                        background_tasks.add_task(
                            create_or_update_on_search_index, garden, settings
                        )
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Entrypoint with DOI {doi}",
            ) from e

        return {"detail": f"Successfully deleted entrypoint with DOI {doi}."}
    else:
        # no error if not found so DELETE is idempotent
        return {"detail": f"No entrypoint found with DOI {doi}."}


@router.put("/{doi:path}", response_model=EntrypointMetadataResponse)
async def create_or_replace_entrypoint(
    doi: str,
    background_tasks: BackgroundTasks,
    entrypoint_data: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    existing_entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)

    if existing_entrypoint is None:
        return await _create_new_entrypoint(entrypoint_data, db, user)

    assert_deletable_by_user(existing_entrypoint, user)
    # re-assign ownership if specified
    if entrypoint_data.owner_identity_id is not None:
        new_owner: User | None = await User.get(
            db, identity_id=entrypoint_data.owner_identity_id
        )
        existing_entrypoint.owner = new_owner or user

    try:
        # naive update with all other values from payload
        for key, value in entrypoint_data.model_dump(
            exclude="owner_identity_id"
        ).items():
            setattr(existing_entrypoint, key, value)

        await db.commit()
        gardens: list[Garden] | None = await get_gardens_for_entrypoint(
            existing_entrypoint, db
        )
        if gardens and settings.SYNC_SEARCH_INDEX:
            for garden in gardens:
                logger.info(msg=f"Sending garden {garden.doi} to search index")
                background_tasks.add_task(
                    create_or_update_on_search_index, garden, settings
                )
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error occurred: {str(e)}",
        ) from e
    return existing_entrypoint


async def _create_new_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession,
    user: User,
) -> Entrypoint:
    # default owner is authed_user unless owner_identity_id is explicitly provided
    owner: User = user
    if entrypoint.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=entrypoint.owner_identity_id
        )
        if explicit_owner is not None:
            owner = explicit_owner
        else:
            logger.warning(
                f"No user found with Globus identity ID {entrypoint.owner_identity_id}. "
                f"Assigning default ownership to {user.identity_id} ({user.username}). "
            )

    new_entrypoint = Entrypoint.from_dict(
        entrypoint.model_dump(exclude="owner_identity_id")
    )
    new_entrypoint.owner = owner
    db.add(new_entrypoint)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entrypoint with this DOI already exists",
        ) from e
    return new_entrypoint
