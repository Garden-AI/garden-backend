from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.entrypoint import (
    EntrypointCreateRequest,
    EntrypointMetadataResponse,
)
from src.models import Entrypoint, User

router = APIRouter(prefix="/entrypoint")


@router.post("", response_model=EntrypointMetadataResponse)
async def add_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    new_entrypoint = Entrypoint.from_dict(entrypoint.model_dump())
    db.add(new_entrypoint)
    try:
        await db.commit()
        await db.refresh(new_entrypoint)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entrypoint with this DOI already exists",
        ) from e
    return new_entrypoint


# note: the ':path' is a starlette converter option to include '/' characters
# from the rest of the path. This also handles encoded '%2F' slashes correctly
# see also: https://www.starlette.io/routing/#path-parameters
@router.get(
    "/{doi:path}",
    status_code=status.HTTP_200_OK,
    response_model=EntrypointMetadataResponse,
)
async def get_entrypoint_by_doi(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
) -> EntrypointMetadataResponse:
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)
    if entrypoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entrypoint not found with DOI {doi}",
        )
    return entrypoint


@router.delete("/{doi:path}", status_code=status.HTTP_200_OK)
async def delete_entrypoint(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)

    if entrypoint is not None:
        await db.delete(entrypoint)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Entrypoint with DOI {doi}",
            ) from e

        return {"detail": f"Successfully deleted entrypoint with DOI {doi}."}
    else:
        # no error if not found so DELETE is idempotent
        return {"detail": f"No entrypoint found with DOI {doi}."}
