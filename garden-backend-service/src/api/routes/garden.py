from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.garden import GardenCreateRequest, GardenMetadataResponse
from src.models import Garden, User, Entrypoint

router = APIRouter(prefix="/garden")


@router.post("", response_model=GardenMetadataResponse)
async def add_garden(
    garden: GardenCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    # collect entrypoints by DOI
    stmt = select(Entrypoint).where(Entrypoint.doi.in_(garden.entrypoint_ids))
    result = await db.execute(stmt)
    entrypoints: list[Entrypoint] = result.scalars().all()

    if len(entrypoints) != len(garden.entrypoint_ids):
        missing_dois = [
            ep.doi for ep in entrypoints if ep.doi not in garden.entrypoint_ids
        ]
        raise HTTPException(
            status_code=404,
            detail=f"Failed to add garden. Could not find entrypoint(s) with DOIs: {missing_dois}",
        )
    new_garden: Garden = Garden.from_dict(garden.model_dump(exclude="entrypoint_ids"))
    new_garden.entrypoints = entrypoints
    db.add(new_garden)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garden with this DOI already exists",
        ) from e
    return new_garden


@router.get(
    "/{doi:path}",
    status_code=status.HTTP_200_OK,
    response_model=GardenMetadataResponse,
)
async def get_garden_by_doi(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
) -> GardenMetadataResponse:
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Garden not found with DOI {doi}",
        )
    return garden


@router.delete("/{doi:path}", status_code=status.HTTP_200_OK)
async def delete_garden(
    doi: str,
    db: AsyncSession = Depends(get_db_session),
    _user: User = Depends(authed_user),
):
    garden: Garden | None = await Garden.get(db, doi=doi)
    if garden is not None:
        await db.delete(garden)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete Garden with DOI {doi}",
            ) from e
        return {"detail": f"Successfully deleted garden with DOI {doi}."}
    else:
        return {"detail": f"No garden found with DOI {doi}."}
