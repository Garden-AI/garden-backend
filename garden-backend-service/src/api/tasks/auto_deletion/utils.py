from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.config import get_settings
from src.modal.utils import stop_modal_app
from src.models import Base, Garden, ModalApp, ModalFunction
from src.models._associations import gardens_modal_functions

logger = get_logger(__name__)


async def mark_entity_for_deletion(
    entity: type[Base],
    session_maker: async_sessionmaker,
) -> int:
    match entity.__tablename__:
        case "gardens":
            return await mark_gardens_for_deletion(session_maker)
        case "modal_apps":
            return await mark_modal_apps_for_deletion(session_maker)
        case _:
            return 0


async def delete_marked_entity(
    entity: type[Garden | ModalApp],
    session_maker: async_sessionmaker,
    interval: timedelta,
    modal_client=None,
) -> int:
    stmt = select(entity).where(entity.marked_for_deletion.isnot(None))

    count = 0
    async with session_maker() as db:
        results = await db.scalars(stmt)
        marked_entities = results.all()
        count = 0
        now = datetime.now()
        for e in marked_entities:
            if now - e.marked_for_deletion > interval:
                if entity.__tablename__ == "modal_apps":
                    # Stop the modal app before deleting it
                    settings = get_settings()
                    try:
                        # Use provided client or skip this step if no client available
                        if modal_client is not None:
                            await stop_modal_app(
                                e.app_name, modal_client, settings, e.modal_app_id
                            )
                            logger.info(
                                f"Stopped modal app {e.app_name} before deletion"
                            )
                        else:
                            logger.warning(
                                f"No modal client provided, skipping stop for app {e.app_name}"
                            )
                            continue
                    except Exception as ex:
                        logger.error(
                            f"Error stopping modal app {e.app_name}: {str(ex)}"
                        )
                        continue
                await db.delete(e)
                count += 1
        await db.commit()

    return count


async def _update_db_records_with_mark(db: AsyncSession, query: Select):
    results = await db.scalars(query)
    entities_to_mark = results.all()
    now = datetime.now()
    count = 0
    for e in entities_to_mark:
        # only update the time stamp if there isn't one already
        if e.marked_for_deletion is None:
            e.marked_for_deletion = now
            count += 1
    await db.commit()
    return count


async def mark_gardens_for_deletion(session_maker):
    stmt = select(Garden).where(Garden.doi_is_draft)
    async with session_maker() as db:
        return await _update_db_records_with_mark(db, stmt)


async def mark_modal_apps_for_deletion(session_maker) -> int:
    used_function_ids = await get_function_ids_used_in_published_gardens(session_maker)

    # find modal apps where none of their functions are used in the publised gardens
    stmt = select(ModalApp).where(
        ~ModalApp.modal_functions.any(ModalFunction.id.in_(used_function_ids))
    )

    async with session_maker() as db:
        return await _update_db_records_with_mark(db, stmt)


async def unmark_marked_gardens(session_maker) -> int:
    stmt = select(Garden).where(Garden.marked_for_deletion.isnot(None))
    count = 0
    async with session_maker() as db:
        results = await db.scalars(stmt)
        marked_gardens = results.all()
        for g in marked_gardens:
            # unmark marked gardens that have been published since they were marked
            if not g.doi_is_draft:
                g.marked_for_deletion = None
                count += 1
        await db.commit()
    return count


async def unmark_marked_modal_apps(session_maker) -> int:
    used_function_ids = await get_function_ids_used_in_published_gardens(session_maker)

    # ModalApps that are marked for deltion and any of their functions are in use by published gardens
    stmt = select(ModalApp).where(
        ModalApp.marked_for_deletion.isnot(None),
        ModalApp.modal_functions.any(ModalFunction.id.in_(used_function_ids)),
    )
    count = 0
    async with session_maker() as db:
        results = await db.scalars(stmt)
        marked_apps = results.all()
        for app in marked_apps:
            app.marked_for_deletion = None
            count += 1
        await db.commit()
    return count


async def get_function_ids_used_in_published_gardens(
    session_maker: async_sessionmaker,
) -> list[int]:
    stmt = (
        select(gardens_modal_functions.c.modal_function_id)
        .join(Garden, Garden.id == gardens_modal_functions.c.garden_id)
        .where(Garden.doi_is_draft.isnot(True), Garden.is_archived.is_(False))
    )
    async with session_maker() as db:
        results = await db.scalars(stmt)
        return list(results.all())
