from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modal import Client
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

router = APIRouter(prefix="/benchmarks")


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

    invocation = await invoke_modal_fn_async(
        body=ModalInvocationRequest(
            **benchmark_request.model_dump(exclude={"benchmark_id", "task_id"})
        ),
        background_tasks=background_tasks,
        user=user,
        settings=settings,
        modal_client=modal_client,
        under_modal_usage_limit=True,  # TODO: decide if we count benchmarks towards usage
        db=db,
    )

    response = BenchmarkResult(
        **invocation.model_dump(),
        benchmark_id=benchmark_request.benchmark_id,
        function_id=benchmark_request.function_id,
    )
    return response


@router.get("/{id}", response_model=BenchmarkResult)
async def get_benchmark_result(
    id: int,
    modal_client: Client = Depends(get_modal_client),
    db: AsyncSession = Depends(get_db_session),
):
    output = await get_modal_invocation_output(
        id,
        modal_client=modal_client,
        db=db,
    )
    # TODO: turn output into correct response
    #  response = BenchmarkResult()
    return output


async def _function_compatible_with_benchmark(
    function_id: int,
    benchmark_id: int,
) -> bool:
    # TODO: implement me!
    return True
