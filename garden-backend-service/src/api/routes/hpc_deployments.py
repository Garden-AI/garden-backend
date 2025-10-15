from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.api.dependencies.auth import authed_user, is_super_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.hpc_deployments import (
    HpcDeploymentCreateRequest,
    HpcDeploymentPatchRequest,
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
    deployment = HpcDeployment.from_dict(
        deployment_data.model_dump(exclude={"endpoint_ids"}, exclude_unset=True)
    )

    if deployment_data.endpoint_ids:
        from src.models.functions.hpc.hpc_endpoints import HpcEndpoint

        endpoints = await db.scalars(
            select(HpcEndpoint).where(HpcEndpoint.id.in_(deployment_data.endpoint_ids))
        )
        deployment.endpoints = list(endpoints.all())

    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    log.info(
        "Created HPC deployment",
        deployment_id=deployment.id,
    )
    response = HpcDeploymentResponse.model_validate(deployment)
    response.endpoint_ids = [e.id for e in deployment.endpoints]
    return response


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
    deployments = list(result.all())

    responses = []
    for deployment in deployments:
        response = HpcDeploymentResponse.model_validate(deployment)
        response.endpoint_ids = [e.id for e in deployment.endpoints]
        responses.append(response)

    return responses


@router.patch("/{id}", response_model=HpcDeploymentResponse)
async def update_hpc_deployment(
    id: int,
    deployment_data: HpcDeploymentPatchRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    is_admin: bool = Depends(is_super_user),
):
    """
    Update an HPC deployment (admin-only).

    Supports updating conda_env_path, user_endpoint_config, and endpoint associations.
    """
    deployment = await db.scalar(
        select(HpcDeployment)
        .options(
            selectinload(HpcDeployment.functions), selectinload(HpcDeployment.endpoints)
        )
        .where(HpcDeployment.id == id)
    )
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Deployment not found with id {id}",
        )

    data = deployment_data.model_dump(exclude={"endpoint_ids"}, exclude_none=True)

    # Update simple fields
    for key, value in data.items():
        setattr(deployment, key, value)

    # Update endpoint associations if provided
    if deployment_data.endpoint_ids is not None:
        from src.models.functions.hpc.hpc_endpoints import HpcEndpoint

        endpoints = await db.scalars(
            select(HpcEndpoint).where(HpcEndpoint.id.in_(deployment_data.endpoint_ids))
        )
        deployment.endpoints = list(endpoints.all())

    await db.commit()
    await db.refresh(deployment)

    response = HpcDeploymentResponse.model_validate(deployment)
    response.endpoint_ids = [e.id for e in deployment.endpoints]

    log.info(
        "Updated HPC deployment",
        deployment_id=id,
        endpoint_count=len(deployment.endpoints),
    )
    return response


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_hpc_deployment(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    is_admin: bool = Depends(is_super_user),
):
    """
    Delete an HPC deployment (admin-only).

    Requirements:
    - Must be super user
    - Deployment must not be used by any functions
    - If deployment has invocation history, deletion will be blocked
    """
    deployment = await db.scalar(
        select(HpcDeployment)
        .options(selectinload(HpcDeployment.functions))
        .where(HpcDeployment.id == id)
    )
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Deployment not found with id {id}",
        )

    # Check if deployment is used by any functions
    if len(deployment.functions) > 0:
        function_ids = [f.id for f in deployment.functions]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete deployment used by {len(deployment.functions)} function(s) (IDs: {function_ids}). Remove functions first.",
        )

    # Attempt deletion
    try:
        await db.delete(deployment)
        await db.commit()
        log.info("Deleted HPC deployment", deployment_id=id)
        return {"detail": f"Successfully deleted HPC deployment {id}"}
    except IntegrityError as e:
        await db.rollback()
        log.warning(
            "Failed to delete HPC deployment due to FK constraint",
            deployment_id=id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete deployment with invocation history. Invocation logs must be preserved.",
        ) from e
