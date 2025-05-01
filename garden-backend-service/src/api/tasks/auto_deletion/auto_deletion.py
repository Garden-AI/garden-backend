import asyncio
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from src.config import Settings
from src.models import Garden, ModalApp

from .utils import (
    delete_marked_entity,
    mark_entity_for_deletion,
    unmark_marked_gardens,
    unmark_marked_modal_apps,
)

logger = get_logger(__name__)


async def auto_deletion_background_task(
    settings: Settings,
    session_maker: async_sessionmaker,
    modal_client=None,
):
    task_interval: timedelta = timedelta(
        seconds=settings.AUTO_DELETION_INTERVAL_SECONDS
    )
    deletion_age_limit: timedelta = timedelta(
        days=settings.AUTO_DELETION_AGE_LIMIT_DAYS
    )

    while True:
        logger.info("Auto-deletion task starting sweep...")
        num_marked_gardens = await mark_entity_for_deletion(
            Garden,
            session_maker,
        )
        num_makred_modal_apps = await mark_entity_for_deletion(
            ModalApp,
            session_maker,
        )

        log = logger.bind(
            num_marked_gardens=num_marked_gardens,
            num_makred_modal_apps=num_makred_modal_apps,
        )
        log.info("Entities marked for deletion")

        logger.info("Unmarking entities that are no longer deletion candidates...")
        num_gardens_unmarked = await unmark_marked_gardens(session_maker)
        num_modal_apps_unmarked = await unmark_marked_modal_apps(session_maker)
        log = logger.bind(
            num_gardens_unmarked=num_gardens_unmarked,
            num_modal_apps_unmarked=num_modal_apps_unmarked,
        )
        log.info("Unmarked entites")

        logger.info(
            f"Deleting marked entities that were marked more than {deletion_age_limit.days} {'days' if deletion_age_limit.days > 1 else 'day'} ago"
        )
        num_gardens_deleted = await delete_marked_entity(
            Garden, session_maker, deletion_age_limit
        )
        num_modal_apps_deleted = await delete_marked_entity(
            ModalApp, session_maker, deletion_age_limit, modal_client
        )

        log = logger.bind(
            num_gardens_deleted=num_gardens_deleted,
            num_modal_apps_deleted=num_modal_apps_deleted,
        )
        log.info("Entities deleted")

        logger.info(f"Auto-deletion task sleeping for {task_interval}")
        await asyncio.sleep(task_interval.seconds)
