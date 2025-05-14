from unittest.mock import AsyncMock, MagicMock

import pytest
from modal_proto import api_pb2

from src.api.schemas.benchmark import (
    BenchmarkRequest,
    BenchmarkResult,
)
from src.modal.utils import AsyncModalJobStatus
from src.models.benchmark import Benchmark, BenchmarkTask


async def create_benchmark_and_task(db_session_maker, function_id) -> (int, int):
    benchmark = Benchmark(id=1, name="Test Benchmark")
    task = BenchmarkTask(benchmark_id=benchmark.id, function_id=function_id)
    async with db_session_maker() as db:
        db.add(benchmark)
        db.add(task)
        await db.commit()
        await db.refresh(benchmark)
        await db.refresh(task)
        return benchmark.id, task.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_benchmark(
    client,
    mock_db_session,
    async_db_session,
    override_authenticated_dependency,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
    override_get_modal_client_dependency,
    mocker,
):
    # mock the modal helpers in the invocations routes
    mock_function = MagicMock()
    mock_function.object_id = "mock_function_id"
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "mock_call_id"
    mock_invocation.pop_function_call_outputs.return_value = MagicMock(
        outputs=[
            api_pb2.FunctionGetOutputsItem(
                result=api_pb2.GenericResult(status=0, data=b"mock_result_data"),
                data_format=api_pb2.DATA_FORMAT_PICKLE,
            )
        ]
    )

    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=mock_invocation,
    )
    mocker.patch(
        "src.modal.utils.estimate_usage",
        return_value=1.0,
    )

    # Create a modal app with at least 1 function
    modal_app_response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert modal_app_response.status_code == 200
    modal_app = modal_app_response.json()
    function_id = modal_app["modal_function_ids"][0]

    # Create the benchmark
    benchmark_id, task_id = await create_benchmark_and_task(
        async_db_session, function_id
    )
    # Run the benchmark
    run_request = BenchmarkRequest(function_id=function_id)
    run_response = await client.post(
        f"/benchmarks/{benchmark_id}/{task_id}", json=run_request.model_dump()
    )
    assert run_response.status_code == 200

    # Check the benchmark results
    results_response = await client.get(f"/benchmarks/{benchmark_id}/{task_id}")
    assert results_response.status_code == 200
    results = results_response.json()
    assert len(results) == 1
    result = BenchmarkResult(**results[0])
    assert result.status == AsyncModalJobStatus.DONE
    assert result.benchmark_id == benchmark_id
    assert result.function_id == function_id
