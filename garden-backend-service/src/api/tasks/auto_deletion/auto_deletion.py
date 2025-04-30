import asyncio
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from src.config import Settings
from src.models import Garden, ModalApp

from .utils import delete_marked_entity, mark_entity_for_deletion

logger = get_logger(__name__)


async def auto_deletion_background_task(
    settings: Settings, session_maker: async_sessionmaker
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
            Garden, session_maker, deletion_age_limit
        )
        num_makred_modal_apps = await mark_entity_for_deletion(
            ModalApp, session_maker, deletion_age_limit
        )
        # TODO: remove sleep, here for development
        await asyncio.sleep(1)

        log = logger.bind(
            num_marked_gardens=num_marked_gardens,
            num_makred_modal_apps=num_makred_modal_apps,
        )
        log.info("Entities marked for deletion")

        logger.info(
            f"Deleting marked entities that were marked more than {deletion_age_limit.days} {"days" if deletion_age_limit.days > 1 else "day"} ago"
        )
        num_gardens_deleted = await delete_marked_entity(
            ModalApp, session_maker, deletion_age_limit
        )
        num_modal_apps_deleted = await delete_marked_entity(
            Garden, session_maker, deletion_age_limit
        )
        # TODO: remove sleep, here for development
        await asyncio.sleep(1)

        log = logger.bind(
            num_gardens_deleted=num_gardens_deleted,
            num_modal_apps_deleted=num_modal_apps_deleted,
        )
        log.info("Entities deleted")

        logger.info(f"Auto-deletion task sleeping for {task_interval}")
        await asyncio.sleep(task_interval.seconds)
