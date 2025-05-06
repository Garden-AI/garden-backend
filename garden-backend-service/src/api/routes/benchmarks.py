from fastapi import APIRouter, BackgroundTasks, Depends

from src.api.dependencies.auth import authed_user
from src.api.routes.modal.invocations import (
    get_modal_invocation_output,
    invoke_modal_fn_async,
)
from src.api.schemas.benchmark import BenchmarkRequest, BenchmarkResult
from src.models import User

router = APIRouter(prefix="/benchmarks")


@router.post("", response_model=BenchmarkResult)
async def run_benchmark(
    body: BenchmarkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(authed_user),
):
    response = await invoke_modal_fn_async(
        body=body,
        background_tasks=background_tasks,
        user=user,
        under_modal_usage_limit=True,  # TODO: decide if we count benchmarks towards usage
    )

    return response


@router.get("/{id}", response_model=list[BenchmarkResult])
async def get_benchmark_result(
    id: int,
):
    output = await get_modal_invocation_output(id)

    return output
