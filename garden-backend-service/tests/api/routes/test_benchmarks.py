import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_benchmarks_empty(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    """Test getting benchmarks when none exist."""
    response = await client.get("/benchmarks")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_benchmark_regular_user_fails(
    client,
    mock_db_session,
    override_authenticated_dependency,
):
    """Test that a regular user cannot create a benchmark result."""
    payload = {
        "benchmark_name": "My Benchmark",
        "benchmark_task_name": "Task 1",
        "metrics": {"score": 99.9, "latency": 10},
    }
    response = await client.post("/benchmarks", json=payload)
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_and_get_benchmark_super_user(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_is_super_user_dependency,
):
    """Test that a super user can create a benchmark result and it can be retrieved."""
    payload = {
        "benchmark_name": "My Benchmark",
        "benchmark_task_name": "Task 1",
        "metrics": {"score": 99.9, "latency": 10},
    }

    # Create
    response = await client.post("/benchmarks", json=payload)
    assert response.status_code == 201
    created_result = response.json()
    assert created_result["benchmark_name"] == payload["benchmark_name"]
    assert created_result["benchmark_task_name"] == payload["benchmark_task_name"]
    assert created_result["metrics"] == payload["metrics"]
    assert "id" in created_result
    assert "timestamp" in created_result

    # Get all
    response = await client.get("/benchmarks")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == created_result["id"]
    assert results[0]["metrics"] == payload["metrics"]
