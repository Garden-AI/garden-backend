import asyncio
from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models import Base, Garden, ModalApp, ModalFunction
from src.models._associations import gardens_modal_functions


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
    entity: type[Base], session_maker: async_sessionmaker, interval: timedelta
) -> int:
    await asyncio.sleep(1)
    return 0


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
    # First get all modal function IDs that are used in gardens
    used_function_ids = select(gardens_modal_functions.c.modal_function_id)

    # Then find modal apps where none of their functions are used
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
    # Subquery for all used modal function IDs
    used_function_ids = select(gardens_modal_functions.c.modal_function_id)
    # ModalApps where marked_for_deletion is not None and any of their functions are in use
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
