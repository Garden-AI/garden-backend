import asyncio
import random
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select

from src.api.dependencies.database import get_db_session
from src.config import Settings, get_settings
from src.models.garden import Garden

router = APIRouter(
    prefix="/load-test",
    tags=["load-test"],
)


async def load_test_task(settings: Settings, sleep_seconds: int):
    """Background task that randomly creates or reads from the database then sleeps for a bit.

    The idea is to test how our async database setup interacts with the rest of the app and event loop
    under heavy load.
    """
    garden_ids = []
    garden = None
    await asyncio.sleep(sleep_seconds)
    async for db in get_db_session(settings):
        if random.random() < 0.5:  # 50% chance of write
            new_garden = Garden(
                title="Load Test Garden",
                description="Created during load test",
                doi=f"10.load-test-{random.randint(1, 1000000)}",
                doi_is_draft=True,
                authors=["Test Author"],
                contributors=[],
                tags=["load-test"],
                publisher="Garden-AI",
                year=str(datetime.now().year),
                language="en",
                version="0.0.1",
                entrypoint_aliases={},
                is_archived=False,
                user_id=1,
            )
            db.add(new_garden)
            await db.commit()
            garden = new_garden
            garden_ids.append(new_garden.id)
        else:
            # Do a read
            stmt = select(Garden).limit(1)
            result = await db.scalars(stmt)
            garden = result.first()
        # clean up any gardens created during this task
        for garden_id in garden_ids:
            garden = await db.get(Garden, garden_id)
            await db.delete(garden) if garden else None
        break  # We only want to do this once

    return garden


@router.get("/{sleep_seconds}")
async def load_test(
    sleep_seconds: int,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    """Simulate a route that passes jobs to a background task"""
    background_tasks.add_task(load_test_task, settings, sleep_seconds)
    return {"status": "ok"}
