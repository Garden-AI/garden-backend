from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.hpc_endpoints import (
    HpcEndpointCreateRequest,
    HpcEndpointPatchRequest,
    HpcEndpointResponse,
)
from src.config import get_settings
from src.models.functions.hpc.hpc_endpoints import HpcEndpoint
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(prefix="/hpc/endpoints")


@router.post("", response_model=HpcEndpointResponse)
async def create_hpc_endpoint(
    endpoint_data: HpcEndpointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    log.info(
        "Creating HPC endpoint", endpoint_name=endpoint_data.name, user=user.username
    )

    endpoint = HpcEndpoint.from_dict(endpoint_data.model_dump(exclude_unset=True))
    endpoint.user = user

    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    log.info(
        "Created HPC endpoint",
        endpoint_id=endpoint.id,
        endpoint_name=endpoint.name,
        owner=user.username,
    )
    return endpoint


@router.get("/{id}", response_model=HpcEndpointResponse)
async def get_hpc_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db_session),
):
    endpoint = await HpcEndpoint.get(db, id=id)
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Endpoint not found with id {id}",
        )
    return endpoint


@router.get("", response_model=list[HpcEndpointResponse])
async def get_hpc_endpoints(
    db: AsyncSession = Depends(get_db_session),
    *,
    limit: int = Query(50, le=100),
) -> list[HpcEndpointResponse]:
    stmt = select(HpcEndpoint)
    result = await db.scalars(stmt.limit(limit))
    return list(result.all())


@router.patch("/{id}", response_model=HpcEndpointResponse)
async def update_hpc_endpoint(
    id: int,
    endpoint_data: HpcEndpointPatchRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    """
    Update an HPC endpoint (owner or admin only).
    """
    endpoint = await db.scalar(select(HpcEndpoint).where(HpcEndpoint.id == id))

    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Endpoint not found with id {id}",
        )

    # Check if user is owner or super user
    if (
        endpoint.owner.identity_id != user.identity_id
        and str(user.identity_id) not in get_settings().SUPER_USERS
    ):
        log.warning(
            "Unauthorized edit attempt",
            endpoint_id=id,
            attempted_by=user.username,
            owner=endpoint.owner.username,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Failed to edit HPC endpoint (not owned by user {user.username})",
        )

    # Update only provided fields (partial update)
    for key, value in endpoint_data.model_dump(exclude_none=True).items():
        setattr(endpoint, key, value)

    await db.commit()
    await db.refresh(endpoint)

    log.info(
        "Updated HPC endpoint",
        endpoint_id=id,
        endpoint_name=endpoint.name,
        user=user.username,
    )
    return endpoint


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_hpc_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    """
    Delete an HPC endpoint (owner or admin only).

    Requirements:
    - Must be owner or super user
    - Endpoint must not be used by any functions

    Note: Invocation logs will be preserved with hpc_endpoint_id set to NULL.
    """
    endpoint = await db.scalar(
        select(HpcEndpoint)
        .options(selectinload(HpcEndpoint.functions))
        .where(HpcEndpoint.id == id)
    )
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Endpoint not found with id {id}",
        )

    # Check if user is owner or super user
    if (
        endpoint.owner.identity_id != user.identity_id
        and str(user.identity_id) not in get_settings().SUPER_USERS
    ):
        log.warning(
            "Unauthorized deletion attempt",
            endpoint_id=id,
            attempted_by=user.username,
            owner=endpoint.owner.username,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Failed to delete HPC endpoint (not owned by user {user.username})",
        )

    # Check if endpoint is used by any functions
    if len(endpoint.functions) > 0:
        function_ids = [f.id for f in endpoint.functions]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete endpoint used by {len(endpoint.functions)} function(s) (IDs: {function_ids}). Remove functions first.",
        )

    # Attempt deletion
    try:
        await db.delete(endpoint)
        await db.commit()
        log.info(
            "Deleted HPC endpoint",
            endpoint_id=id,
            endpoint_name=endpoint.name,
            user=user.username,
        )
        return {"detail": f"Successfully deleted HPC endpoint {id}"}
    except IntegrityError as e:
        await db.rollback()
        log.warning(
            "Failed to delete HPC endpoint due to constraint violation",
            endpoint_id=id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete endpoint due to a constraint violation.",
        ) from e
