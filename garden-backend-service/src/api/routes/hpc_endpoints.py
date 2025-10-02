from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.hpc_endpoints import (
    HpcEndpointCreateRequest,
    HpcEndpointResponse,
)
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
    log.info("Creating HPC endpoint", endpoint_name=endpoint_data.name)

    # TODO: Add admin-only check here?

    endpoint = HpcEndpoint.from_dict(endpoint_data.model_dump(exclude_unset=True))

    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    log.info(
        "Created HPC endpoint", endpoint_id=endpoint.id, endpoint_name=endpoint.name
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
