from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user, get_auth_client
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import (
    archive_on_datacite,
    assert_deletable_by_user,
    assert_editable_by_user,
    get_gardens_for_entrypoint,
)
from src.api.schemas.entrypoint import (
    EntrypointCreateRequest,
    EntrypointMetadataResponse,
    EntrypointPatchRequest,
)
from src.api.tasks import SearchIndexOperation, schedule_search_index_update
from src.config import Settings, get_settings
from src.models import Entrypoint, Garden, User

logger = get_logger(__name__)

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
    doi: list[str] | None = Query(None),
    tags: list[str] | None = Query(None),
    authors: list[str] | None = Query(None),
    owner_uuid: UUID | None = Query(None),
    draft: bool | None = Query(None),
    year: str | None = Query(None),
    limit: int = Query(50, le=100),
) -> list[EntrypointMetadataResponse]:
    """Fetch multiple entrypoints according to query parameters."""
    stmt = select(Entrypoint)
    if doi:
        stmt = stmt.where(Entrypoint.doi.in_(doi))
    if tags:
        stmt = stmt.where(Entrypoint.tags.overlap(array(tags)))
    if authors:
        stmt = stmt.where(Entrypoint.authors.overlap(array(authors)))
    if owner_uuid:
        stmt = stmt.join(Entrypoint.owner).where(User.identity_id == owner_uuid)
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
    app_auth_client=Depends(get_auth_client),
):
    log = logger.bind(doi=doi)
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
                        log.info(
                            "Scheduled background task",
                            operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
                            garden_doi=garden.doi,
                        )
                        background_tasks.add_task(
                            schedule_search_index_update,
                            SearchIndexOperation.CREATE_OR_UPDATE,
                            garden,
                            settings,
                            db,
                            app_auth_client,
                        )
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Entrypoint with DOI {doi}",
            ) from e
        log.info("Successfully deleted entrypoint")
        return {"detail": f"Successfully deleted entrypoint with DOI {doi}."}
    else:
        # no error if not found so DELETE is idempotent
        log.info("No entrypoint to delete")
        return {"detail": f"No entrypoint found with DOI {doi}."}


@router.put("/{doi:path}", response_model=EntrypointMetadataResponse)
async def create_or_replace_entrypoint(
    doi: str,
    background_tasks: BackgroundTasks,
    entrypoint_data: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    app_auth_client=Depends(get_auth_client),
):
    log = logger.bind(doi=doi)
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
        log.info(
            "Assigned entrypoint ownership",
            owner_identity_id=(new_owner or user).identity_id,
            owner_username=(new_owner or user).username,
        )

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
                background_tasks.add_task(
                    schedule_search_index_update,
                    SearchIndexOperation.CREATE_OR_UPDATE,
                    garden,
                    settings,
                    db,
                    app_auth_client,
                )
                log.info(
                    "Scheduled background task",
                    garden_doi=garden.doi,
                    operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
                )
        log.info("Updated entrypoint in DB")
    except IntegrityError as e:
        log.exception("Failed to update entrypoint", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error occurred: {str(e)}",
        ) from e
    return existing_entrypoint


@router.patch("/{doi:path}", response_model=EntrypointMetadataResponse)
async def update_entrypoint(
    doi: str,
    entrypoint_data: EntrypointPatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: User = Depends(authed_user),
    app_auth_client=Depends(get_auth_client),
) -> EntrypointMetadataResponse:
    log = logger.bind(doi=doi)
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)
    if entrypoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Entrypoint with DOI {doi} found.",
        )

    assert_editable_by_user(entrypoint, entrypoint_data, user)

    for key, value in entrypoint_data.model_dump(exclude_none=True).items():
        setattr(entrypoint, key, value)

    if entrypoint.is_archived and entrypoint.doi_is_draft:
        log.warning("Could not archive entrypoint from draft state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot archive a entrypoint in draft state.",
        )

    # Prevent updating certain fields if entrypoint is published
    if not entrypoint.doi_is_draft:
        entrypoint_patch_dict = entrypoint_data.model_dump(exclude_none=True)
        restricted_attrs = [
            attr
            for attr in [
                "func_uuid",
                "container_uuid",
                "full_image_uri",
                "base_image_uri",
                "notebook_url",
                "short_name",
                "function_text",
            ]
            if attr in entrypoint_patch_dict
        ]
        if restricted_attrs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update a published entrypoint's attribute(s): {', '.join(restricted_attrs)}.",
            )

    await db.commit()
    log.info("Updated entrypoint")
    if entrypoint.is_archived:
        await archive_on_datacite(doi, settings)

    if settings.SYNC_SEARCH_INDEX:
        gardens: list[Garden] | None = await get_gardens_for_entrypoint(entrypoint, db)
        for garden in gardens:
            background_tasks.add_task(
                schedule_search_index_update,
                SearchIndexOperation.CREATE_OR_UPDATE,
                garden,
                settings,
                db,
                app_auth_client,
            )
            log.info(
                "Scheduled background task",
                garden_doi=garden.doi,
                operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
            )

    return entrypoint


async def _create_new_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession,
    user: User,
) -> Entrypoint:
    # default owner is authed_user unless owner_identity_id is explicitly provided
    log = logger.bind(doi=entrypoint.doi)
    owner: User = user
    if entrypoint.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=entrypoint.owner_identity_id
        )
        if explicit_owner is not None:
            log.info(
                "Assigned entrypoint ownership to other user",
                owner_identity_id=entrypoint.owner_identity_id,
                owner_username=explicit_owner.username,
            )
            owner = explicit_owner
        else:
            log.warning(
                "Could not assign ownership to unknown user",
                unknown_id=entrypoint.owner_identity_id,
            )

    new_entrypoint = Entrypoint.from_dict(
        entrypoint.model_dump(exclude="owner_identity_id")
    )
    new_entrypoint.owner = owner
    db.add(new_entrypoint)
    try:
        await db.commit()
    except IntegrityError as e:
        log.exception()
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entrypoint with this DOI already exists",
        ) from e
    log.info("Saved new entrypoint")
    return new_entrypoint
