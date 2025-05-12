from unittest.mock import AsyncMock, MagicMock

import pytest
from modal_proto import api_pb2

from src.api.schemas.benchmark import (
    BenchmarkCreateRequest,
    BenchmarkRequest,
    BenchmarkResult,
)
from src.modal.utils import AsyncModalJobStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_benchmark(
    client,
    mock_db_session,
    override_authenticated_dependency,
    mock_modal_publisher_auth_state,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # Create a modal app with at least 1 function
    modal_app_response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert modal_app_response.status_code == 200
    modal_app = modal_app_response.json()
    function_id = modal_app["modal_function_ids"][0]

    # Create the benchmark
    create_request = BenchmarkCreateRequest(function_id=function_id)
    benchmark_response = await client.post(
        "/benchmarks/create", json=create_request.model_dump()
    )
    assert benchmark_response.status_code == 201

    # We should get back the metadata for the function acting as the benchmark
    benchmark = benchmark_response.json()
    assert benchmark == modal_app["modal_functions"][0]

    duplicate_create_response = await client.post(
        "/benchmarks/create", json=create_request.model_dump()
    )
    assert (
        duplicate_create_response.status_code == 409
    ), "Creating a benchmark that already exists should fail"

    # Check that we can pull the benchmark's metadata
    metadata_response = await client.get("/benchmarks")
    assert metadata_response.status_code == 200
    benchmark_meta = metadata_response.json()
    assert len(benchmark_meta) == 1, "There should one benchmark"
    assert benchmark_meta[0] == benchmark, "It should be the benchmark we created"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_benchmark(
    client,
    mock_db_session,
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
    benchmark_id = modal_app["modal_function_ids"][0]
    function_id = modal_app["modal_function_ids"][0]

    # Create the benchmark
    create_request = BenchmarkCreateRequest(function_id=function_id)
    benchmark_response = await client.post(
        "/benchmarks/create", json=create_request.model_dump()
    )
    assert benchmark_response.status_code == 201

    # Run the benchmark
    run_request = BenchmarkRequest(
        function_id=function_id,
        task_id=0,
    )
    run_response = await client.post(
        f"/benchmarks/{benchmark_id}", json=run_request.model_dump()
    )
    assert run_response.status_code == 200

    # Check the benchmark results
    results_response = await client.get(f"/benchmarks/{benchmark_id}")
    assert results_response.status_code == 200
    results = results_response.json()
    assert len(results) == 1
    result = BenchmarkResult(**results[0])
    assert result.status == AsyncModalJobStatus.DONE
    assert result.benchmark_id == benchmark_id
    assert result.function_id == function_id
