import asyncio
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from src.config import Settings

logger = get_logger(__name__)


async def auto_deletion_background_task(
    settings: Settings, session_maker: async_sessionmaker
):
    interval = timedelta(seconds=settings.AUTO_DELETION_INTERVAL_SECONDS)
    while True:
        logger.info("Auto-deletion task starting sweep...")

        # simulate some stuff that takes a bit
        await asyncio.sleep(1)

        logger.info(f"Auto-deletion task sleeping for {interval}")
        await asyncio.sleep(interval.total_seconds())
