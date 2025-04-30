import asyncio
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models import Base


async def mark_entity_for_deletion(
    entity: type[Base],
    session_maker: async_sessionmaker,
) -> int:
    await asyncio.sleep(1)
    return 0


async def delete_marked_entity(
    entity: type[Base], session_maker: async_sessionmaker, interval: timedelta
) -> int:
    await asyncio.sleep(1)
    return 0
