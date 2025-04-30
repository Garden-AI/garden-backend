import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

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


async def mark_gardens_for_deletion(session_maker):
    stmt = select(Garden).where(Garden.doi_is_draft)
    async with session_maker() as db:
        results = await db.scalars(stmt)
        gardens_to_mark = results.all()
        now = datetime.now()
        for g in gardens_to_mark:
            g.marked_for_deletion = now
        await db.commit()
    return len(gardens_to_mark)


async def mark_modal_apps_for_deletion(session_maker) -> int:
    # First get all modal function IDs that are used in gardens
    used_function_ids = select(gardens_modal_functions.c.modal_function_id)

    # Then find modal apps where none of their functions are used
    stmt = select(ModalApp).where(
        ~ModalApp.modal_functions.any(ModalFunction.id.in_(used_function_ids))
    )

    async with session_maker() as db:
        results = await db.scalars(stmt)
        apps_to_mark = results.all()
        now = datetime.now()
        for app in apps_to_mark:
            app.marked_for_deletion = now
        await db.commit()
    return len(apps_to_mark)
