from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.hpc_deployments import (
    HpcDeploymentCreateRequest,
    HpcDeploymentResponse,
)
from src.models.functions.hpc.hpc_deployments import HpcDeployment
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(prefix="/hpc/deployments")


@router.post("", response_model=HpcDeploymentResponse)
async def create_hpc_deployment(
    deployment_data: HpcDeploymentCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    deployment = HpcDeployment.from_dict(deployment_data.model_dump(exclude_unset=True))

    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    log.info(
        "Created HPC deployment",
        deployment_id=deployment.id,
    )
    return deployment


@router.get("/{id}", response_model=HpcDeploymentResponse)
async def get_hpc_deployment(
    id: int,
    db: AsyncSession = Depends(get_db_session),
):
    deployment = await HpcDeployment.get(db, id=id)
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Deployment not found with id {id}",
        )
    return deployment


@router.get("", response_model=list[HpcDeploymentResponse])
async def get_hpc_deployments(
    db: AsyncSession = Depends(get_db_session),
    *,
    limit: int = Query(50, le=100),
) -> list[HpcDeploymentResponse]:
    stmt = select(HpcDeployment)
    result = await db.scalars(stmt.limit(limit))
    return list(result.all())
