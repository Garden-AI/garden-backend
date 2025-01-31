import asyncio
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

import src.logging  # noqa  # import to ensure logger is configured
from src.api.dependencies.database import (
    async_init,
    get_db_session_maker,
    get_session,
)
from src.api.routes import (
    docker_push_token,
    doi,
    entrypoints,
    gardens,
    greet,
    hello_database,
    modal,
    notebook,
    users,
)
from src.api.routes.mdf import search as mdf_search
from src.config import Settings, get_settings
from src.middleware.logging import (
    add_error_handling_middleware,
    add_process_time_middleware,
    add_request_id_middleware,
)
from src.models.garden import Garden

# def get_db_session_maker(settings: Settings) -> async_sessionmaker[AsyncSession]:
#     postgres_url = settings.SQLALCHEMY_DATABASE_URL
#     engine = create_async_engine(postgres_url, echo=False)
#     return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    session_maker = await get_db_session_maker(settings=settings)

    # Set Modal env variables
    os.environ["MODAL_TOKEN_ID"] = settings.MODAL_TOKEN_ID
    os.environ["MODAL_TOKEN_SECRET"] = settings.MODAL_TOKEN_SECRET

    # load text-search sql
    await async_init(session_maker, Path(settings.GARDEN_SEARCH_SQL_DIR))

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add our custom middleware
add_error_handling_middleware(app)
add_process_time_middleware(app)
add_request_id_middleware(app)

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(hello_database.router)
app.include_router(entrypoints.router)
app.include_router(gardens.router)
app.include_router(users.router)

app.include_router(modal.invocations.router)
app.include_router(modal.modal_apps.router)
app.include_router(modal.modal_functions.router)
app.include_router(modal.modal_file_metadata.router)

app.include_router(mdf_search.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}


async def load_test_task(settings: Settings, sleep_seconds: int):
    """Background task that randomly creates or reads from the database then sleeps for a bit.

    The idea is to test how our async database setup interacts with the rest of the app and event loop
    under heavy load.
    """
    async with get_session() as db:
        if random.random() < 0.5:  # 50% chance of write
            new_garden = Garden(
                name="Load Test Garden",
                description="Created during load test",
            )
            db.add(new_garden)
            await db.commit()
        # Do a read
        stmt = select(Garden).limit(1)
        result = await db.scalars(stmt)
        garden = result.first()
    await asyncio.sleep(sleep_seconds)
    return garden


@app.get("/load-test/{sleep_seconds}")
async def load_test(
    sleep_seconds: int,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    """Simulate a route that passes jobs to a background task"""
    background_tasks.add_task(load_test_task, settings, sleep_seconds)
    return {"status": "ok"}
