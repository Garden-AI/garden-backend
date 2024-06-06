from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.entrypoint import (
    EntrypointCreateRequest,
    EntrypointMetadataResponse,
)
from src.models import (
    User,
    Entrypoint,
)

router = APIRouter(prefix="/entrypoint")


# note: the ':path' is a starlette converter option to include '/' characters
# from the rest of the path.
# see also: https://www.starlette.io/routing/#path-parameters
@router.get("/{doi:path}", response_model=EntrypointMetadataResponse)
async def get_entrypoint(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
):
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)
    if entrypoint is None:
        raise HTTPException(
            status_code=404, detail=f"Entrypoint not found with DOI {doi}"
        )
    return entrypoint.to_dict()


@router.post("", response_model=EntrypointMetadataResponse)
async def post_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    new_entrypoint = Entrypoint.from_dict(entrypoint.model_dump())
    db.add(new_entrypoint)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Entrypoint with this DOI already exists"
        )
    return new_entrypoint


@router.put("/{doi:path}", response_model=EntrypointMetadataResponse)
async def put_entrypoint(
    doi: str,
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    existing_entrypoint = await Entrypoint.get(db, doi=doi)
    if existing_entrypoint is None:
        raise HTTPException(
            status_code=404, detail=f"Entrypoint not found with DOI {doi}"
        )

    for key, value in entrypoint.model_dump().items():
        setattr(existing_entrypoint, key, value)

    await db.commit()
    return existing_entrypoint
