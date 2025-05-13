import pickle

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from modal import Client
from modal._serialization import deserialize
from src.api.dependencies.auth import authed_user, under_modal_usage_limit
from src.api.dependencies.database import get_db_session
from src.api.dependencies.modal import get_modal_client
from src.api.routes.modal.invocations import (
    get_modal_invocation_output,
    invoke_modal_fn_async,
)
from src.api.schemas.benchmark import (
    BenchmarkCreateRequest,
    BenchmarkMetadata,
    BenchmarkRequest,
    BenchmarkResult,
)
from src.api.schemas.modal.invocations import ModalInvocationRequest
from src.config import Settings, get_settings
from src.modal.status import AsyncModalJobStatus
from src.models import User
from src.models.benchmark import Benchmark, BenchmarkRun
from src.models.modal.invocations import ModalInvocationLog, ModalInvocationResult
from src.models.modal.modal_function import ModalFunction

router = APIRouter(prefix="/benchmarks")

logger = get_logger(__name__)


@router.get("", response_model=list[BenchmarkMetadata])
async def get_benchmark_metadata(
    db: AsyncSession = Depends(get_db_session),
):
    """Get metadata about available benchmarks"""
    query = select(ModalFunction).join(
        Benchmark, ModalFunction.id == Benchmark.function_id
    )
    results = await db.scalars(query)
    return results.all()


@router.post(
    "/create",
    response_model=BenchmarkMetadata,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark(
    create_request: BenchmarkCreateRequest,
    user: User = Depends(authed_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Register a function as a benchmark"""
    if existing_benchmark := await Benchmark.get(
        db, function_id=create_request.function_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Benchmark {existing_benchmark.function_id} already exists!",
        )

    function = await ModalFunction.get(db, id=create_request.function_id)
    if function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Function {create_request.function_id} does not exist!",
        )

    # Create the benchmark record
    benchmark = Benchmark(
        function_id=function.id,
    )
    db.add(benchmark)
    await db.commit()
    await db.refresh(benchmark)
    log = logger.bind(benchmark_id=benchmark.id, function_id=function.id)
    log.info("Benchmark created")

    # Return the function since the benchmark record just points to the function anyway
    return function


@router.post("/{id}", response_model=BenchmarkResult)
async def run_benchmark(
    id: int,
    benchmark_request: BenchmarkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
    modal_client: Client = Depends(get_modal_client),
    under_modal_usage_limit: bool = Depends(under_modal_usage_limit),
):
    """Request a new run of the benchmark"""
    compatible = await _function_compatible_with_benchmark(
        function_id=benchmark_request.function_id,
        benchmark_id=id,
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
        function_id=id,  # The benchmark function to run
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
        under_modal_usage_limit=under_modal_usage_limit,
        db=db,
    )

    logger.info("Recording benchmark run in database")
    # Create a record in the benchmark_runs table
    benchmark_run = BenchmarkRun(
        benchmark_function_id=id,
        function_id=benchmark_request.function_id,
        invocation_id=invocation.id,
        task_id=benchmark_request.task_id,
    )
    db.add(benchmark_run)
    await db.commit()
    await db.refresh(benchmark_run)

    # Convert the invocation response to a dictionary
    invocation_data = invocation.model_dump()

    response = BenchmarkResult(
        benchmark_id=id,
        function_id=benchmark_request.function_id,
        **invocation_data,
    )
    return response


@router.get("/{benchmark_id}", response_model=list[BenchmarkResult])
async def get_results_for_benchmark(
    benchmark_id: int,
    modal_client: Client = Depends(get_modal_client),
    db: AsyncSession = Depends(get_db_session),
):
    """Return a list of results for the benchmark"""
    # subquery to get the latest run of given benchmark for each function that has been benchmarked
    latest_runs_subq = (
        select(
            BenchmarkRun.function_id,
            # Using func.max to get the latest invocation per function_id
            func.max(ModalInvocationLog.date_invoked).label("latest_date"),
        )
        .join(
            ModalInvocationResult,
            BenchmarkRun.invocation_id == ModalInvocationResult.id,
        )
        .join(ModalInvocationLog, ModalInvocationResult.log_id == ModalInvocationLog.id)
        .where(BenchmarkRun.benchmark_function_id == benchmark_id)
        .group_by(BenchmarkRun.function_id)
        .subquery()
    )

    # Main query to get the BenchmarkRun with the latest date for each function, attach the date it was invoked
    query = (
        select(BenchmarkRun, ModalInvocationLog.date_invoked)
        .join(
            ModalInvocationResult,
            BenchmarkRun.invocation_id == ModalInvocationResult.id,
        )
        .join(ModalInvocationLog, ModalInvocationResult.log_id == ModalInvocationLog.id)
        .join(
            latest_runs_subq,
            (BenchmarkRun.function_id == latest_runs_subq.c.function_id)
            & (ModalInvocationLog.date_invoked == latest_runs_subq.c.latest_date),
        )
        .where(BenchmarkRun.benchmark_function_id == benchmark_id)
    )

    results = await db.execute(query)
    benchmark_runs_with_date = results.all()

    benchmark_results = await _get_results_for_runs(
        benchmark_runs_with_date, db, modal_client, logger
    )
    return benchmark_results


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


async def _get_results_for_runs(
    benchmark_runs,
    db: AsyncSession,
    modal_client: Client,
    logger,
) -> list[BenchmarkResult]:
    """"""
    results = []
    for benchmark_run, date_invoked in benchmark_runs:
        try:
            # Get the invocation result
            invocation_output = await get_modal_invocation_output(
                benchmark_run.invocation_id, modal_client, db
            )
            if not invocation_output:
                # Skip runs with missing invocation output
                logger.warning(
                    "Invocation output not found",
                    benchmark_run_id=benchmark_run.id,
                    invocation_id=benchmark_run.invocation_id,
                )
                continue

            # Initialize result to None
            invocation_result = None

            # The status is already an AsyncModalJobStatus enum value
            status = invocation_output.get("status", AsyncModalJobStatus.PENDING)

            # Only try to deserialize if we have a completed run with a result
            if (
                status is AsyncModalJobStatus.DONE
                and "result" in invocation_output
                and invocation_output["result"]
            ):
                try:
                    invocation_result = deserialize(
                        invocation_output["result"].data, modal_client
                    )
                except Exception as e:
                    logger.error(
                        "Failed to deserialize invocation result",
                        benchmark_run_id=benchmark_run.id,
                        invocation_id=benchmark_run.invocation_id,
                        error=str(e),
                    )

            # Create the benchmark result
            result = BenchmarkResult(
                benchmark_id=benchmark_run.benchmark_id,
                function_id=benchmark_run.function_id,
                status=status,
                result=invocation_result,
                date_invoked=date_invoked,
            )
            results.append(result)
        except Exception as e:
            # Catch any other exceptions to prevent entire request from failing
            logger.error(
                "Error processing benchmark run",
                benchmark_run_id=benchmark_run.id,
                error=str(e),
            )
            # Continue to next benchmark run
            continue
    return results
