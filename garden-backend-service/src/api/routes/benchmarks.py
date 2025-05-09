import pickle

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from modal import Client
from modal._serialization import deserialize
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.dependencies.modal import get_modal_client
from src.api.routes.modal.invocations import (
    get_modal_invocation_output,
    invoke_modal_fn_async,
)
from src.api.schemas.benchmark import BenchmarkRequest, BenchmarkResult
from src.api.schemas.modal.invocations import ModalInvocationRequest
from src.config import Settings, get_settings
from src.models import User
from src.models.benchmark import BenchmarkRun

router = APIRouter(prefix="/benchmarks")

logger = get_logger(__name__)


@router.post("", response_model=BenchmarkResult)
async def run_benchmark(
    benchmark_request: BenchmarkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
    modal_client: Client = Depends(get_modal_client),
):
    compatible = await _function_compatible_with_benchmark(
        benchmark_request.function_id,
        benchmark_request.benchmark_id,
    )
    if not compatible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Function {body.function_id} is not compatible with requested benchmark {body.benchmark_id}",
        )

    logger.info("Creating invocation request.")
    # Populate args_kwargs_serialized if not provided
    args_kwargs_serialized = await _populate_args_kwargs_serialized(benchmark_request)

    # Create the invocation request
    invocation_request = ModalInvocationRequest(
        function_id=benchmark_request.benchmark_id,  # The benchmark function to run
        args_kwargs_serialized=args_kwargs_serialized,
        args_blob_id=benchmark_request.args_blob_id,
    )

    logger.info("Invoking benchmark function.")
    # Invoke the benchmark function async
    invocation = await invoke_modal_fn_async(
        body=invocation_request,
        background_tasks=background_tasks,
        user=user,
        settings=settings,
        modal_client=modal_client,
        under_modal_usage_limit=True,  # TODO: decide if we count benchmarks towards usage
        db=db,
    )

    logger.info("Recording benchmark run in database")
    # Create a record in the benchmark_runs table
    benchmark_run = BenchmarkRun(
        benchmark_id=benchmark_request.benchmark_id,
        function_id=benchmark_request.function_id,
        invocation_id=invocation.id,
        task_id=benchmark_request.task_id,
    )
    db.add(benchmark_run)
    await db.commit()
    await db.refresh(benchmark_run)

    # Convert the invocation response to a dictionary
    invocation_data = invocation.model_dump()
    del invocation_data["id"]

    # Return the response with both benchmark and function IDs
    response = BenchmarkResult(
        id=benchmark_run.id,
        benchmark_id=benchmark_request.benchmark_id,
        function_id=benchmark_request.function_id,
        **invocation_data,
    )
    return response


@router.get("/{id}", response_model=BenchmarkResult)
async def get_benchmark_result(
    id: int,  # benchmark run id, not function id
    modal_client: Client = Depends(get_modal_client),
    db: AsyncSession = Depends(get_db_session),
):
    # Find the benchmark run associated with this invocation
    query = select(BenchmarkRun).where(BenchmarkRun.id == id)
    result = await db.execute(query)
    benchmark_run = result.scalars().first()

    if not benchmark_run:
        # No benchmark run record, so we don't know which function was benchmarked
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invocation {id} is not associated with a benchmark run",
        )

    # Get the invocation result
    invocation_output = await get_modal_invocation_output(
        benchmark_run.invocation_id, modal_client, db
    )
    if not invocation_output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invocation result for benchmark run {benchmark_run.id} not found",
        )

    # Deserialize modal result
    invocation_result = deserialize(invocation_output["result"].data, modal_client)

    # Create the benchmark result by adding the benchmark-specific fields
    response = BenchmarkResult(
        id=benchmark_run.id,
        benchmark_id=benchmark_run.benchmark_id,
        function_id=benchmark_run.function_id,
        status=invocation_output["status"],
        result=invocation_result,
    )
    return response


async def _function_compatible_with_benchmark(
    function_id: int,
    benchmark_id: int,
) -> bool:
    # TODO: implement me!
    return True


async def _populate_args_kwargs_serialized(request: BenchmarkRequest) -> bytes:
    """
    Populate the args_kwargs_serialized field if not provided by the client.

    Args:
        request: The benchmark request containing optional args_kwargs_serialized

    Returns:
        The args_kwargs_serialized bytes to use for the invocation
    """
    if request.args_kwargs_serialized:
        # If client provided serialized args, use them as-is
        return request.args_kwargs_serialized

    # Create a minimal valid pickle for empty args and kwargs
    # Modal expects the args format to be a tuple of (args, kwargs)
    # where args is a list and kwargs is a dict
    return pickle.dumps(([], {}))
