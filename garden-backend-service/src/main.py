import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import src.logging  # noqa  # import to ensure logger is configured
from src.api.dependencies.database import (
    async_init,
    get_db_session_maker,
)
from src.api.routes import (
    docker_push_token,
    doi,
    entrypoints,
    gardens,
    greet,
    hello_database,
    load_test,
    modal,
    notebook,
    users,
)
from src.api.routes.mdf import search as mdf_search
from src.api.tasks.auto_deletion import auto_deletion_background_task
from src.config import get_settings
from src.middleware.logging import (
    add_error_handling_middleware,
    add_process_time_middleware,
    add_request_id_middleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    session_maker = await get_db_session_maker(settings=settings)

    # Set Modal env variables
    os.environ["MODAL_TOKEN_ID"] = settings.MODAL_TOKEN_ID
    os.environ["MODAL_TOKEN_SECRET"] = settings.MODAL_TOKEN_SECRET

    # load text-search sql
    await async_init(session_maker, Path(settings.GARDEN_SEARCH_SQL_DIR))

    # Include load test routes only in development environments
    if settings.GARDEN_ENV in ["dev", "local"]:
        app.include_router(load_test.router)

    # kick off long-running auto-deletion task
    # dont await it, we want it to keep running while we move on
    asyncio.create_task(auto_deletion_background_task(settings, session_maker))

    # Everything before this yield happens on startup
    yield
    # Eveything after the yield happens on shutdown


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
