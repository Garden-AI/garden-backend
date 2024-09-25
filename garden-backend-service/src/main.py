import asyncio
from contextlib import asynccontextmanager

import src.logging  # noqa  # import to ensure logger is configured
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.api.routes import (
    docker_push_token,
    doi,
    entrypoints,
    garden_search_record,
    gardens,
    greet,
    hello_database,
    modal,
    notebook,
    status,
    users,
    modal_apps,
)
from src.api.routes.mdf import search as mdf_search
from src.api.tasks import retry_failed_updates
from src.auth.globus_auth import get_auth_client
from src.config import Settings, get_settings
from src.middleware.logging import LogProcessTimeMiddleware, LogRequestIdMiddleware


def get_db_session_maker(settings: Settings) -> async_sessionmaker[AsyncSession]:
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=False)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kick of the search index synchronization loop
    settings = get_settings()
    db_session = get_db_session_maker(settings=settings)
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
app.add_middleware(LogProcessTimeMiddleware)
app.add_middleware(LogRequestIdMiddleware)

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(garden_search_record.router)
app.include_router(hello_database.router)
app.include_router(entrypoints.router)
app.include_router(gardens.router)
app.include_router(modal_apps.router)
app.include_router(users.router)
app.include_router(status.router)

app.include_router(modal.invocations.router)

app.include_router(mdf_search.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
