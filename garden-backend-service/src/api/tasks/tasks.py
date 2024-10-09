import asyncio
from datetime import datetime
from enum import Enum

from globus_sdk import ConfidentialAppAuthClient, SearchAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.api.dependencies.search import get_globus_search_client
from src.api.schemas.garden import GardenMetadataResponse
from src.config import Settings
from src.models import FailedSearchIndexUpdate, Garden

logger = get_logger(__name__)


class SearchIndexOperation(Enum):
    CREATE_OR_UPDATE = "create_or_update"
    DELETE = "delete"


class SearchIndexUpdateError(Exception):
    """Custom exception for search index update failures."""

    def __init__(self, message, doi):
        super().__init__(message)
        self.doi = doi


async def schedule_search_index_update(
    update_operation: SearchIndexOperation,
    garden: Garden,
    settings: Settings,
    db: AsyncSession,
    auth_client: ConfidentialAppAuthClient,
) -> None:
    """Schedule an update on the search index for the given garden."""
    logger.info(
        "Scheduled search index update",
        update_operation=update_operation.value,
        garden_doi=garden.doi,
    )
    try:
        match update_operation:
            case SearchIndexOperation.CREATE_OR_UPDATE:
                await _create_or_update_on_search_index(
                    garden, settings, db, auth_client
                )
            case SearchIndexOperation.DELETE:
                await _delete_from_search_index(garden.doi, settings, db, auth_client)
            case _:
                pass

        # Look for stale FailedSearchIndexUpdate records with this doi
        update: FailedSearchIndexUpdate | None = await FailedSearchIndexUpdate.get(
            db, doi=garden.doi
        )
        if update is not None:
            # delete the record from the failed updates table
            await db.delete(update)
        await db.commit()
    except SearchIndexUpdateError as e:
        logger.warning(
            "Failed to update search index",
            doi=garden.doi,
            operation_type=update_operation.value,
            error_message=str(e),
        )
        # The update failed, log the failure
        failed_update = FailedSearchIndexUpdate(
            doi=garden.doi,
            operation_type=update_operation.value,
            error_message=str(e),
            retry_count=0,
        )
        await _log_failed_update(failed_update, db)
        await db.commit()


async def retry_failed_updates(
    settings: Settings,
    db_session: async_sessionmaker,
    auth_client: ConfidentialAppAuthClient,
) -> None:
    """Periodically retry failed updates to the search index."""
    while settings.SYNC_SEARCH_INDEX:
        try:
            async with db_session() as db:
                failed_updates = await _get_failed_updates(db, settings)
                successful, failed = await _process_failed_updates(
                    failed_updates, db, settings, auth_client
                )
            logger.debug(
                "Processed failed updates", successful=successful, failed=failed
            )
        except asyncio.CancelledError:
            logger.warning("Synchronization loop canceled.")
            break
        except Exception:
            logger.exception("Error in synchronization loop", exc_info=True)

        await asyncio.sleep(settings.RETRY_INTERVAL_SECS)


async def _process_failed_updates(
    failed_updates: list[FailedSearchIndexUpdate],
    db: AsyncSession,
    settings: Settings,
    auth_client: ConfidentialAppAuthClient,
) -> tuple[int, int]:
    """Attempt to update the search index for each failed update.

    If the update to the search index fails, log the failure.

    Returns: (int, int): number of successful updates, number of failed updates
    """
    successful = 0
    failed = 0

    for update in failed_updates:
        garden: Garden | None = await Garden.get(db, doi=update.doi)
        try:
            await _try_update(update, garden, settings, db, auth_client)
            # If the update was successful, delete the record
            await db.delete(update)
            await db.commit()
            successful += 1
        except SearchIndexUpdateError as e:
            # The update failed, update the record and continue
            logger.warning(
                "Failed to update search index",
                doi=update.doi,
                error_message=str(e),
            )
            update.error_message = str(e)
            await _log_failed_update(update, db)
            await db.commit()
            failed += 1

    return successful, failed


async def _get_failed_updates(
    db: AsyncSession,
    settings: Settings,
) -> list[FailedSearchIndexUpdate]:
    """Retrieve failed updates with retry count less than max retry."""
    result = await db.scalars(
        select(FailedSearchIndexUpdate)
        .where(FailedSearchIndexUpdate.retry_count < settings.MAX_RETRY_COUNT)
        .order_by(FailedSearchIndexUpdate.last_attempt)
    )
    return result.all()


async def _try_update(
    update: FailedSearchIndexUpdate,
    garden: Garden | None,
    settings: Settings,
    db: AsyncSession,
    auth_client: ConfidentialAppAuthClient,
) -> None:
    """Handle a single update operation based on its type.

    Raises:
       SearchIndexUpdateError
    """
    if (
        update.operation_type == SearchIndexOperation.CREATE_OR_UPDATE.value
        and garden is not None
    ):
        # Only update a garden that still exists
        await _create_or_update_on_search_index(garden, settings, db, auth_client)
    else:
        # Otherwise it has been deleted
        await _delete_from_search_index(update.doi, settings, db, auth_client)


async def _log_failed_update(
    update: FailedSearchIndexUpdate,
    db: AsyncSession,
) -> None:
    """Log a failed update attempt."""
    logger.info("Recording failed search index update", doi=update.doi)
    existing_update: FailedSearchIndexUpdate | None = await FailedSearchIndexUpdate.get(
        db, doi=update.doi
    )
    if existing_update is None:
        # Create a new record
        db.add(update)
    else:
        logger.info("Recording failed search index update", doi=update.doi)
        # Update the existing record
        existing_update.retry_count += 1
        existing_update.error_message = update.error_message
        existing_update.operation_type = update.operation_type
        existing_update.last_attempt = datetime.now()
    await db.commit()


async def _create_or_update_on_search_index(
    garden: Garden,
    settings: Settings,
    db: AsyncSession,
    auth_client: ConfidentialAppAuthClient,
) -> None:
    """Create or update a record on the search index.

    Raises:
       SearchIndexUpdateError
    """
    try:
        client = get_globus_search_client(auth_client)
        garden_pub = GardenMetadataResponse.model_validate(garden, from_attributes=True)
        garden_meta = {
            "subject": garden_pub.doi,
            "visible_to": ["public"],
            "content": garden_pub.model_dump(mode="json"),
        }

        create_result = client.create_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_meta,
        )

        if create_result.http_status != 200:
            raise SearchIndexUpdateError(
                f"Failed updating garden {garden.doi} on search index: {create_result}",
                garden.doi,
            )
    except SearchAPIError as e:
        raise SearchIndexUpdateError(
            f"Failed updating garden {garden.doi} on search index: {str(e)}", garden.doi
        )


async def _delete_from_search_index(
    garden_doi: str,
    settings: Settings,
    db: AsyncSession,
    auth_client: ConfidentialAppAuthClient,
) -> None:
    """Delete a record from the search index.

    Raises:
       SearchIndexUpdateError
    """
    try:
        client = get_globus_search_client(auth_client)
        delete_result = client.delete_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_doi,
        )
        if delete_result.http_status != 200:
            raise SearchIndexUpdateError(
                f"Failed deleting garden {garden_doi} from search index: {delete_result}",
                garden_doi,
            )
    except SearchAPIError as e:
        raise SearchIndexUpdateError(
            f"Failed deleting garden {garden_doi} from search index: {str(e)}",
            garden_doi,
        )
