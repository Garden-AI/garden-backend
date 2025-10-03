from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.hpc_invocations import (
    HpcInvocationCreateRequest,
    HpcInvocationResponse,
)
from src.models.functions.hpc.hpc_endpoints import HpcEndpoint
from src.models.functions.hpc.hpc_functions import HpcFunction
from src.models.functions.hpc.hpc_invocations import HpcInvocationLog
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(prefix="/hpc")


@router.post(
    "/invocations",
    response_model=HpcInvocationResponse,
)
async def create_hpc_invocation(
    create_request: HpcInvocationCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    """Create a new HPC function invocation log entry."""
    log.info("Creating HPC invocation log...")

    # Verify the function exists
    hpc_function = await HpcFunction.get(db, id=create_request.function_id)
    if hpc_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Function not found with id {create_request.function_id}",
        )

    # Verify the endpoint exists and get its database ID
    result = await db.execute(
        select(HpcEndpoint).where(
            HpcEndpoint.gcmu_id == create_request.endpoint_gcmu_id
        )
    )
    hpc_endpoint = result.scalar_one_or_none()
    if hpc_endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HPC Endpoint not found with gcmu_id {create_request.endpoint_gcmu_id}",
        )

    # Create the invocation log
    invocation_log = HpcInvocationLog(
        user_id=user.id,
        function_id=create_request.function_id,
        hpc_endpoint_id=hpc_endpoint.id,
        globus_task_id=create_request.globus_task_id,
        date_invoked=datetime.now(),
        user_endpoint_config=create_request.user_endpoint_config,
    )

    db.add(invocation_log)
    await db.commit()
    await db.refresh(invocation_log)

    log.info(
        "Created HPC invocation log",
        invocation_id=invocation_log.id,
        function_id=create_request.function_id,
    )

    return invocation_log


@router.get("/invocations", response_model=list[HpcInvocationResponse])
async def get_hpc_invocations(
    db: AsyncSession = Depends(get_db_session),
):
    """Get all HPC invocations."""
    stmt = select(HpcInvocationLog)
    result = await db.scalars(stmt)
    return list(result.all())
