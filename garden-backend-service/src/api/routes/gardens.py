import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from globus_sdk import ConfidentialAppAuthClient
from sqlalchemy import desc, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, array
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user, get_auth_client
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import (
    archive_on_datacite,
    assert_deletable_by_user,
    assert_editable_by_user,
    is_doi_registered,
)
from src.api.schemas.garden import (
    Facets,
    GardenCreateRequest,
    GardenMetadataResponse,
    GardenPatchRequest,
    GardenSearchRequest,
    GardenSearchResponse,
)
from src.api.tasks import SearchIndexOperation, schedule_search_index_update
from src.config import Settings, get_settings
from src.models import Entrypoint, Garden, ModalFunction, User

logger = get_logger(__name__)
router = APIRouter(prefix="/gardens")


@router.post("", response_model=GardenMetadataResponse)
async def add_garden(
    garden: GardenCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    app_auth_client: ConfidentialAppAuthClient = Depends(get_auth_client),
):
    log = logger.bind(doi=garden.doi)
    new_garden = await _create_new_garden(garden, db, user)
    if settings.SYNC_SEARCH_INDEX:
        log.info(
            "Scheduled background task",
            operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
        )
        background_tasks.add_task(
            schedule_search_index_update,
            SearchIndexOperation.CREATE_OR_UPDATE,
            new_garden,
            settings,
            db,
            app_auth_client,
        )
    return new_garden


@router.get("", response_model=list[GardenMetadataResponse])
async def search_gardens(
    doi: Annotated[list[str] | None, Query()] = None,
    draft: Annotated[bool | None, Query()] = None,
    owner_uuid: Annotated[UUID | None, Query()] = None,
    authors: Annotated[list[str] | None, Query()] = None,
    contributors: Annotated[list[str] | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    year: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(le=100)] = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch multiple gardens according to query parameters"""
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

    # Apply filter to query
    try:
        stmt = _apply_filters(Garden, stmt, search_request.filters)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Do the ranked full-text search
    if search_query := search_request.q:
        await _register_search_function(db)
        search_func = func.search_gardens(search_query).table_valued(
            "garden_id", "rank"
        )
        stmt = stmt.join(search_func, search_func.c.garden_id == Garden.id).order_by(
            search_func.c.rank
        )

    # Get totals for offset/pagination
    total_count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = await db.scalar(total_count_stmt)

    # Run the query
    result = await db.scalars(
        stmt.limit(search_request.limit).offset(search_request.offset)
    )
    gardens = result.all()

    # Get the facet information
    facets = await _calculate_facets(db)

    return GardenSearchResponse(
        count=len(gardens),
        total=total_count,
        offset=search_request.offset,
        garden_meta=gardens,
        facets=facets,
    )


def _apply_filters(cls, stmt, filters):
    for filter in filters:
        if not hasattr(cls, filter.field_name):
            raise ValueError(f"Invalid filter field_name: {filter.field_name}")
        for value in filter.values:
            if type(getattr(cls, filter.field_name).type) is ARRAY:
                stmt = stmt.where(
                    func.array_to_string(getattr(cls, filter.field_name), " ").match(
                        value
                    )
                )
            else:
                stmt = stmt.where(
                    func.cast(getattr(cls, filter.field_name), TEXT).match(value)
                )
    return stmt


async def _register_search_function(session):
    search_function_sql = """
    -- Do a ranked full-text search on gardens and entrypoints
    -- Gardens are ranked by their relevance to the search plus their entrypoints relevance to the search
    CREATE OR REPLACE FUNCTION search_gardens(search_query TEXT)
    RETURNS TABLE (garden_id int, rank real) AS $$
    DECLARE
        query tsquery := websearch_to_tsquery(search_query);
    BEGIN
        RETURN QUERY
        WITH entrypoints_weighted_documents AS (
            SELECT id,
            setweight(to_tsvector(array_to_string(e.authors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(e.tags, ' ')), 'B') ||
            setweight(to_tsvector(e.title), 'D') ||
            setweight(to_tsvector(e.description), 'D') AS ep_document
            FROM entrypoints e
        ), gardens_weighted_documents AS (
            SELECT g.id AS garden_id,
            setweight(to_tsvector(array_to_string(g.authors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(g.contributors, ' ')), 'A') ||
            setweight(to_tsvector(array_to_string(g.tags, ' ')), 'B') ||
            setweight(to_tsvector(g.description), 'D') ||
            setweight(to_tsvector(g.title), 'D') AS garden_document
            FROM gardens g
        ), garden_entrypoint_ranks AS (
            SELECT gwd.garden_id,
                   ts_rank(gwd.garden_document, query) AS garden_rank,
                   SUM(ts_rank(ep.ep_document, query)) AS total_entrypoint_rank
            FROM gardens_weighted_documents gwd
            LEFT JOIN gardens_entrypoints ge ON gwd.garden_id = ge.garden_id
            LEFT JOIN entrypoints_weighted_documents ep ON ep.id = ge.entrypoint_id
            GROUP BY gwd.garden_id, gwd.garden_document
        )
        SELECT ger.garden_id, ger.garden_rank + COALESCE(ger.total_entrypoint_rank, 0) AS rank
        FROM garden_entrypoint_ranks ger
        WHERE garden_rank > 0 OR COALESCE(total_entrypoint_rank, 0) > 0
        ORDER BY rank DESC;
    END;
    $$ LANGUAGE plpgsql;
    """

    await session.execute(text(search_function_sql))
    await session.commit()


async def _calculate_facets(db: AsyncSession) -> Facets:
    # For `tags` and `authors`, we need to unnest arrays and count distinct elements
    tags_stmt = (
        select(func.unnest(Garden.tags).label("tag"), func.count().label("count"))
        .filter(Garden.tags.isnot(None))
        .group_by("tag")
        .order_by(desc("count"))
    )
    authors_stmt = (
        select(func.unnest(Garden.authors).label("author"), func.count().label("count"))
        .filter(Garden.authors.isnot(None))
        .group_by("author")
        .order_by(desc("count"))
    )

    # For `year`, just count by distinct year values
    year_stmt = (
        select(Garden.year, func.count(Garden.year).label("count"))
        .filter(Garden.year.isnot(None))
        .group_by(Garden.year)
        .order_by(desc("count"))
    )

    # Execute all queries concurrently for better performance
    tags_result, authors_result, year_result = await asyncio.gather(
        db.execute(tags_stmt),
        db.execute(authors_stmt),
        db.execute(year_stmt),
    )

    # Transform results into dictionaries for easier consumption
    tags = {row[0]: row[1] for row in tags_result.all()}
    authors = {row[0]: row[1] for row in authors_result.all()}
    year = {str(row[0]): row[1] for row in year_result.all()}

    return Facets(tags=tags, authors=authors, year=year)


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
    app_auth_client: ConfidentialAppAuthClient = Depends(get_auth_client),
):
    log = logger.bind(doi=doi)
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is not None:
        assert_deletable_by_user(garden, user)
        await db.delete(garden)
        try:
            await db.commit()
            if settings.SYNC_SEARCH_INDEX:
                log.info(
                    "Scheduled background task",
                    operation_type=SearchIndexOperation.DELETE.value,
                )
                background_tasks.add_task(
                    schedule_search_index_update,
                    SearchIndexOperation.DELETE,
                    garden,
                    settings,
                    db,
                    app_auth_client,
                )
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


@router.put("/{doi:path}", response_model=GardenMetadataResponse)
async def create_or_replace_garden(
    doi: str,
    background_tasks: BackgroundTasks,
    garden_data: GardenCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    app_auth_client: ConfidentialAppAuthClient = Depends(get_auth_client),
):
    log = logger.bind(doi=doi)

    existing_garden: Garden | None = await Garden.get(db, doi=doi)
    if existing_garden is None:
        new_garden = await _create_new_garden(garden_data, db, user)
        if settings.SYNC_SEARCH_INDEX:
            log.info(
                "Scheduled background task",
                operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
            )
            background_tasks.add_task(
                schedule_search_index_update,
                SearchIndexOperation.CREATE_OR_UPDATE,
                new_garden,
                settings,
                db,
                app_auth_client,
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
        log.info(
            "Assigned garden ownership",
            owner_identity_id=(new_owner or user).identity_id,
            owner_username=(new_owner or user).username,
        )

    # update related entrypoints
    new_entrypoints = await _collect_entrypoints(garden_data.entrypoint_ids, db)
    existing_garden.entrypoints = new_entrypoints

    # naive update with remaining values from payload
    for key, value in garden_data.model_dump(
        exclude={"owner_identity_id", "entrypoint_ids", "modal_function_ids"}
    ).items():
        setattr(existing_garden, key, value)
    try:
        await db.commit()
        if settings.SYNC_SEARCH_INDEX:
            log.info("Updating garden on search index")
            background_tasks.add_task(
                schedule_search_index_update,
                SearchIndexOperation.CREATE_OR_UPDATE,
                existing_garden,
                settings,
                db,
                app_auth_client,
            )
    except IntegrityError as e:
        log.exception("Failed to update garden", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error occurred: {str(e)}",
        ) from e

    return existing_garden


@router.patch("/{doi:path}", response_model=GardenMetadataResponse)
async def update_garden(
    doi: str,
    garden_data: GardenPatchRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    app_auth_client=Depends(get_auth_client),
) -> GardenMetadataResponse:
    log = logger.bind(doi=doi)
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Garden with DOI {doi} found.",
        )

    assert_editable_by_user(garden, garden_data, user)

    garden_patch_dict = garden_data.model_dump(exclude_none=True)

    # Prevent updating entrypoints on published gardens
    if "entrypoint_ids" in garden_patch_dict:
        if not garden.doi_is_draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a published garden's entrypoints.",
            )
        # collect entrypoints by DOI
        garden.entrypoints = await _collect_entrypoints(garden_data.entrypoint_ids, db)

    for key, value in garden_patch_dict.items():
        setattr(garden, key, value)

    if garden.is_archived and garden.doi_is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot archive a garden in draft state.",
        )

    try:
        await db.commit()
        if garden.is_archived:
            await archive_on_datacite(doi, settings)
            log.info("Archived garden on datacite")

        if settings.SYNC_SEARCH_INDEX:
            log.info(
                "Scheduled background task",
                operation_type=SearchIndexOperation.CREATE_OR_UPDATE.value,
            )
            background_tasks.add_task(
                schedule_search_index_update,
                SearchIndexOperation.CREATE_OR_UPDATE,
                garden,
                settings,
                db,
                app_auth_client,
            )
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
    db: AsyncSession,
    user: User,
):
    log = logger.bind(doi=garden_data.doi)
    # if not specified, check draft status with the real world (doi.org)
    if garden_data.doi_is_draft is None:
        registered = await is_doi_registered(garden_data.doi)
        garden_data.doi_is_draft = not registered

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
            exclude={"entrypoint_ids", "modal_function_ids", "owner_identity_id"}
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
