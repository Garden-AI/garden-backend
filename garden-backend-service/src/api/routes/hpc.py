from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import assert_editable_by_user
from src.api.schemas.hpc import (
    HpcFunctionCreateRequest,
    HpcFunctionMetadataResponse,
    HpcFunctionPatchRequest,
)
from src.models._associations import (
    gardens_hpc_functions,
)
from src.models.functions.hpc.hpc_deployments import HpcDeployment
from src.models.functions.hpc.hpc_functions import HpcFunction
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(prefix="/hpc")


@router.post(
    "/functions",
    response_model=HpcFunctionMetadataResponse,
)
async def create_hpc_function(
    create_request: HpcFunctionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    log.info("Creating hpc function...")
    deployments = await _collect_deployments(create_request.deployment_ids, db)
    func = HpcFunction.from_dict(
        create_request.model_dump(exclude=["deployment_ids"], exclude_unset=True)
    )
    func.name = create_request.function_name
    func.user = user
    func.deployments = deployments
    db.add(func)
    await db.commit()
    await db.refresh(func)
    return func


@router.get("/functions", response_model=list[HpcFunctionMetadataResponse])
async def get_hpc_functions(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    stmt = (
        select(HpcFunction)
        .outerjoin(
            gardens_hpc_functions,
            HpcFunction.id == gardens_hpc_functions.c.hpc_function_id,
        )
        .where(
            (HpcFunction.user_id == user.id)
            | (gardens_hpc_functions.c.garden_id.is_not(None))
        )
        .distinct()
    )
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/functions/{id}", response_model=HpcFunctionMetadataResponse)
async def get_hpc_function(
    id: int,
    db: AsyncSession = Depends(get_db_session),
):
    hpc_function = await HpcFunction.get(db, id=id)
    if hpc_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Function not found with id {id}",
        )
    return hpc_function


@router.patch("/functions/{id}", response_model=HpcFunctionMetadataResponse)
async def update_hpc_function(
    id: int,
    function_data: HpcFunctionPatchRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    hpc_function = await HpcFunction.get(db, id=id)
    if hpc_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No HPC Function with ID {id} found.",
        )

    assert_editable_by_user(hpc_function, function_data, user)

    for key, value in function_data.model_dump(
        exclude={"deployment_ids"}, exclude_none=True
    ).items():
        setattr(hpc_function, key, value)

    deployments = await _collect_deployments(function_data.deployment_ids or [], db)
    hpc_function.deployments = deployments
    await db.commit()
    log.info("Updated HPC Function", id=id)

    return hpc_function


async def _collect_deployments(ids: list[int], db: AsyncSession) -> list[HpcDeployment]:
    stmt = select(HpcDeployment).where(HpcDeployment.id in ids)
    results = await db.scalars(stmt)
    return results.all()
