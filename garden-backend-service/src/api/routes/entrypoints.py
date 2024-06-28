from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, RelationshipProperty
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import assert_deletable_by_user
from src.api.schemas.entrypoint import (
    EntrypointCreateRequest,
    EntrypointMetadataResponse,
)
from src.models import Base, Entrypoint, User

logger = getLogger(__name__)

router = APIRouter(prefix="/entrypoints")


@router.post("", response_model=EntrypointMetadataResponse)
async def add_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    return await _create_new_entrypoint(entrypoint, db, user)


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
    user: User = Depends(authed_user),
):
    entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)

    if entrypoint is not None:
        assert_deletable_by_user(entrypoint, user)
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


@router.put("/{doi:path}", response_model=EntrypointMetadataResponse)
async def put_entrypoint_by_doi(
    doi: str,
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    if entrypoint.doi != doi:
        raise HTTPException(
            status=status.HTTP_400_BAD_REQUEST,
            detail="payload DOI does not match request URL",
        )

    existing_entrypoint: Entrypoint | None = await Entrypoint.get(db, doi=doi)
    if existing_entrypoint is None:
        return await _create_new_entrypoint(entrypoint, db, user)

    if existing_entrypoint.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this entrypoint.",
        )

    # current owner can change the owner ID to someone else
    if entrypoint.owner_identity_id:
        new_owner: User | None = await User.get(
            db, identity_id=entrypoint.owner_identity_id
        )
        if new_owner:
            existing_entrypoint.owner = new_owner

    # update with values from payload, creating new objects for papers, datasets etc.
    for key, value in entrypoint.model_dump(exclude="owner_identity_id").items():
        orm_attribute: QueryableAttribute = getattr(Entrypoint, key)
        is_relationship = isinstance(orm_attribute.property, RelationshipProperty)
        # handle one-many relationships (i.e. the related metadata types)
        if isinstance(value, list) and is_relationship:
            related_cls: Base = orm_attribute.property.mapper.class_
            new_items: list[Base] = [related_cls.from_dict(item) for item in value]
            setattr(existing_entrypoint, key, new_items)
        else:
            setattr(existing_entrypoint, key, value)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update entrypoint with doi {doi}",
        ) from e


async def _create_new_entrypoint(
    entrypoint: EntrypointCreateRequest,
    db: AsyncSession,
    user: User,
):
    # default owner is authed_user unless owner_identity_id is explicitly provided
    owner: User = user
    if entrypoint.owner_identity_id is not None:
        explicit_owner: User | None = await User.get(
            db, identity_id=entrypoint.owner_identity_id
        )
        if explicit_owner is not None:
            owner = explicit_owner
        else:
            logger.warning(
                f"No user found with Globus identity ID {entrypoint.owner_identity_id}. "
                f"Assigning default ownership to {user.identity_id} ({user.username}). "
            )

    new_entrypoint = Entrypoint.from_dict(
        entrypoint.model_dump(exclude="owner_identity_id")
    )
    new_entrypoint.owner = owner
    db.add(new_entrypoint)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entrypoint with this DOI already exists",
        ) from e
    return new_entrypoint
