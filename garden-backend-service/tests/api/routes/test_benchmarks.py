import pytest

from src.api.schemas.benchmark import BenchmarkCreateRequest


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
