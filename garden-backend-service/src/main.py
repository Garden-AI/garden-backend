import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.dependencies.database import get_db_session_maker
from src.api.routes import (
    docker_push_token,
    doi,
    entrypoints,
    garden_search_record,
    gardens,
    greet,
    hello_database,
    notebook,
    status,
    users,
)
from src.api.tasks import retry_failed_updates
from src.auth.globus_auth import get_auth_client
from src.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kick of the search index synchronization loop
    settings = get_settings()
    db_session = await get_db_session_maker(settings=settings)
    auth_client = get_auth_client()

    if settings.SYNC_SEARCH_INDEX:
        task = asyncio.create_task(
            retry_failed_updates(settings, db_session, auth_client)
        )
        yield
        task.cancel()
    else:
        yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(garden_search_record.router)
app.include_router(hello_database.router)
app.include_router(entrypoints.router)
app.include_router(gardens.router)
app.include_router(users.router)
app.include_router(status.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
