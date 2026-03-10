import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

import src.logging  # noqa  # import to ensure logger is configured
from src.api.dependencies.database import (
    async_init,
    get_db_session_maker,
)
from src.api.dependencies.modal import get_modal_client
from src.api.routes import (
    benchmarks,
    docker_push_token,
    entrypoints,
    gardens,
    greet,
    hello_database,
    hpc,
    hpc_endpoints,
    hpc_invocations,
    load_test,
    modal,
    notebook,
    users,
)
from src.api.routes.mcp.search import mcp
from src.api.tasks.auto_deletion import auto_deletion_background_task
from src.config import get_settings
from src.middleware.logging import (
    AddRequestIDMiddleware,
    ErrorHandlingMiddleware,
    HeaderLoggingMiddleware,
    ProcessTimeMiddleware,
)

logger = get_logger(__name__)


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

    # Try to create modal client for auto-deletion task
    modal_client = None
    try:
        modal_client = await get_modal_client(settings)
    except Exception as e:
        logger.warning(f"Failed to create modal client at startup: {e}")

    deletion_task = None
    if modal_client is not None:
        # kick off long-running auto-deletion task
        # dont await it, we want it to keep running while we move on
        deletion_task = asyncio.create_task(
            auto_deletion_background_task(settings, session_maker, modal_client)
        )

    # Everything before this yield happens on startup
    yield
    # Eveything after the yield happens on shutdown
    if deletion_task is not None:
        deletion_task.cancel()


app = FastAPI(lifespan=lifespan)

# Add middleware in reverse execution order (last added = first to execute)
# CORSMiddleware must be outermost to ensure CORS headers are added to ALL responses,
# including error responses from ErrorHandlingMiddleware
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(AddRequestIDMiddleware)
app.add_middleware(HeaderLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(greet.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(hello_database.router)
app.include_router(entrypoints.router)
app.include_router(gardens.router)
app.include_router(users.router)
app.include_router(benchmarks.router)

app.include_router(modal.invocations.router)
app.include_router(modal.modal_apps.router)
app.include_router(modal.modal_functions.router)
app.include_router(modal.modal_file_metadata.router)

app.include_router(hpc.router)
app.include_router(hpc_endpoints.router)
app.include_router(hpc_invocations.router)

app.mount("/mcp-http", mcp.streamable_http_app())
app.mount("/mcp-sse", mcp.sse_app())


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
