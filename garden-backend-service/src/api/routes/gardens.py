from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import (
    assert_citable,
    assert_deletable_by_user,
    assert_editable_by_user,
)
from src.api.schemas.garden import (
    GardenCreateRequest,
    GardenMetadataResponse,
    GardenPatchRequest,
    GardenSearchRequest,
    GardenSearchResponse,
    GardenState,
)
from src.api.search.utils import apply_filters, calculate_facets, sort_results
from src.config import Settings, get_settings
from src.datacite.doi_utils import (
    archive_doi,
    mint_draft_doi,
    publish_doi,
    update_doi_metadata,
)
from src.models import Entrypoint, Garden, ModalFunction, User

logger = get_logger(__name__)
router = APIRouter(prefix="/gardens")


class StateTransition(str, Enum):
    PUBLISH = "PUBLISH"
    ARCHIVE = "ARCHIVE"


@router.post("", response_model=GardenMetadataResponse)
async def add_garden(
    garden: GardenCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    # If the user has provided a DOI, too bad. We're ignoring it.
    # We need to guarantee that we're using our own DOIs so we
    # can update them at will.
    doi = await mint_draft_doi(settings)
    new_garden = await _create_new_garden(garden, doi, db, user)
    return new_garden


@router.get("", response_model=list[GardenMetadataResponse], operation_id="search_gardens")
async def search_gardens(
    doi: Annotated[list[str] | None, Query()] = None,
    draft: Annotated[bool | None, Query()] = None,
    owner_uuid: Annotated[UUID | None, Query()] = None,
    authors: Annotated[list[str] | None, Query()] = None,
    contributors: Annotated[list[str] | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    year: Annotated[str | None, Query()] = None,
    function_ids: Annotated[list[int] | None, Query()] = None,
    limit: Annotated[int | None, Query(le=100)] = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch multiple gardens according to query parameters.

    If function_ids is provided, only search for gardens using those functions.
    Otherwise, perform a general search using the other parameters.
    """
    # Handle function-specific search
    if function_ids is not None:
        stmt = select(Garden).where(
            Garden.modal_functions.any(ModalFunction.id.in_(function_ids))
        )
        result = await db.scalars(stmt.limit(limit))
        gardens = result.all()
        return gardens

    # Handle general search
    stmt = select(Garden)

    if doi is not None:
        stmt = stmt.where(Garden.doi.in_(doi))

    if draft is not None:
        stmt = stmt.where(Garden.doi_is_draft == draft)

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


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
    response_model=GardenSearchResponse,
)
async def search(
    search_request: GardenSearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> GardenSearchResponse:
    stmt = select(Garden)

    # Apply filters to query
    try:
        stmt = apply_filters(Garden, stmt, search_request.filters)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Do a ranked full-text search
    if search_query := search_request.q:
        search_func = func.search_gardens(search_query).table_valued(
            "garden_id", "rank"
        )
        stmt = stmt.join(search_func, search_func.c.garden_id == Garden.id).order_by(
            search_func.c.rank
        )

    # Calculate facets after applying the filters and searching
    facets = await calculate_facets(db, stmt)

    # Get totals for offset/pagination
    total_count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = await db.scalar(total_count_stmt)

    stmt = stmt.limit(search_request.limit).offset(search_request.offset)

    if search_request.sort:
        try:
            stmt = sort_results(Garden, stmt, search_request.sort)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Run the search query
    result = await db.scalars(stmt)
    gardens = result.all()

    return GardenSearchResponse(
        count=len(gardens),
        total=total_count,
        offset=search_request.offset,
        garden_meta=gardens,
        facets=facets,
    )


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
    log = logger.bind(doi=doi)
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
        log.info("Deleted garden from database")
        return {"detail": f"Successfully deleted garden with DOI {doi}."}
    else:
        log.info("No garden to delete")
        return {"detail": f"No garden found with DOI {doi}."}


def _determine_state_change(
    current_garden: Garden, requested_change: GardenPatchRequest
) -> StateTransition | None:
    """Determine if a valid state transition is being requested.

    Args:
        current_garden: The current garden state
        requested_change: The requested changes

    Returns:
        StateTransition if a valid transition is requested, None otherwise

    Raises:
        HTTPException: If an invalid state transition is requested
    """
    current_state = current_garden.state
    target_state = requested_change.target_state
    if current_state is target_state or target_state is None:
        # no transition required
        return None

    match (current_state, target_state):
        case (GardenState.DRAFT, GardenState.PUBLISHED):
            return StateTransition.PUBLISH
        case (GardenState.PUBLISHED, GardenState.ARCHIVED):
            return StateTransition.ARCHIVE
        case (GardenState.DRAFT, GardenState.ARCHIVED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Garden is in a DRAFT state, so it can simply be deleted instead of archived.",
            )
        case _:
            # otherwise, this is requesting a "backwards" transition, which is not allowed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition Garden from {current_state.value} back to {target_state.value} state.",
            )


@router.patch("/{doi:path}", response_model=GardenMetadataResponse)
async def update_garden(
    doi: str,
    garden_patch_data: GardenPatchRequest,
    user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GardenMetadataResponse:
    log = logger.bind(doi=doi)
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Garden with DOI {doi} found.",
        )

    if garden.state is GardenState.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Garden with DOI {doi} is archived and cannot be edited.",
        )

    assert_editable_by_user(garden, garden_patch_data, user)
    assert_citable(garden, garden_patch_data)

    # Determine if a state transition is being requested
    state_transition = _determine_state_change(garden, garden_patch_data)

    garden_patch_dict = garden_patch_data.model_dump(
        exclude_none=True, exclude={"target_state"}
    )

    if "entrypoint_ids" in garden_patch_dict:
        # collect entrypoints by DOI
        garden.entrypoints = await _collect_entrypoints(
            garden_patch_dict["entrypoint_ids"] or [], db
        )

    if "modal_function_ids" in garden_patch_dict:
        garden.modal_functions = await _collect_modal_functions(
            garden_patch_dict["modal_function_ids"] or [], db
        )

    for key, value in garden_patch_dict.items():
        setattr(garden, key, value)

    try:
        # Make sure DataCite change goes through before committing DB.
        match state_transition:
            case StateTransition.ARCHIVE:
                await archive_doi(garden, settings)
                log.info("Archived garden DOI on datacite")
            case StateTransition.PUBLISH:
                await publish_doi(garden, settings)
                log.info("Published garden DOI on datacite")
            case _:
                await update_doi_metadata(garden, settings)
                log.info("Updated garden metadata on datacite")

        await db.commit()

    except Exception as e:
        log.exception("Failed to update garden")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error occurred: {str(e)}",
        ) from e
    log.info("Successfully updated garden")
    return garden


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


async def _collect_modal_functions(
    ids: list[int], db: AsyncSession
) -> list[ModalFunction]:
    stmt = select(ModalFunction).where(ModalFunction.id.in_(ids))
    result = await db.execute(stmt)
    modal_functions: list[ModalFunction] = result.scalars().all()

    if len(modal_functions) != len(ids):
        missing_ids = [mf.id for mf in modal_functions if mf.id not in ids]
        raise HTTPException(
            status_code=404,
            detail=f"Could not find modal function(s) with IDs: {missing_ids}",
        )
    return modal_functions


async def _create_new_garden(
    garden_data: GardenCreateRequest,
    doi: str,
    db: AsyncSession,
    user: User,
):
    log = logger.bind(doi=doi)
    garden_data.doi = doi
    garden_data.doi_is_draft = True
    garden_data.is_archived = False

    # collect entrypoints by DOI
    entrypoints = await _collect_entrypoints(garden_data.entrypoint_ids, db)
    # collect modal functions by ID
    modal_functions = await _collect_modal_functions(garden_data.modal_function_ids, db)

    # default owner is authed_user unless owner_identity_id is explicitly provided
    owner: User = user
    if garden_data.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=garden_data.owner_identity_id
        )
        if explicit_owner is not None:
            log.info(
                "Assigned garden ownership to other user",
                owner_identity_id=garden_data.owner_identity_id,
                owner_username=explicit_owner.username,
            )
            owner = explicit_owner
        else:
            log.warning(
                "Could not assign ownership to unknown user",
                unknown_id=garden_data.owner_identity_id,
            )

    new_garden: Garden = Garden.from_dict(
        garden_data.model_dump(
            exclude={
                "entrypoint_ids",
                "modal_function_ids",
                "owner_identity_id",
                "state",
            }
        )
    )

    new_garden.owner = owner
    new_garden.entrypoints = entrypoints
    new_garden.modal_functions = modal_functions

    db.add(new_garden)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Could not create new garden: {e}",
        ) from e
    log.info("Created new garden")
    return new_garden
