import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.logging  # noqa  # import to ensure logger is configured
from src.api.dependencies.database import async_init
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
    ErrorHandlingMiddleware,
    LogProcessTimeMiddleware,
    LogRequestIdMiddleware,
)


def get_db_session_maker(settings: Settings) -> async_sessionmaker[AsyncSession]:
    postgres_url = settings.SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(postgres_url, echo=False)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_session = get_db_session_maker(settings=settings)

    # Set Modal env variables
    os.environ["MODAL_TOKEN_ID"] = settings.MODAL_TOKEN_ID
    os.environ["MODAL_TOKEN_SECRET"] = settings.MODAL_TOKEN_SECRET

    # load text-search sql
    await async_init(db_session, Path(settings.GARDEN_SEARCH_SQL_DIR))

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LogProcessTimeMiddleware)
app.add_middleware(LogRequestIdMiddleware)

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

app.include_router(mdf_search.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
