from typing import Any, Dict

from pydantic import Base64Bytes

from src.api.schemas.base import BaseSchema
from src.modal.status import AsyncModalJobStatus


class BenchmarkRequest(BaseSchema):
    # The id of the benchmark to run, for now it is a modal function id
    benchmark_id: int
    # The id of the benchmarking task to run, i.e. Benchmark: MatBecnch Discovery -> Task: IS2RE
    task_id: int
    # The id of the function to benchmark
    function_id: int

    args_kwargs_serialized: Base64Bytes | None = None
    args_blob_id: str | None = None


class BenchmarkResult(BaseSchema):
    # ID of the invocation
    id: int

    # Status of the job
    status: AsyncModalJobStatus

    # Error message if any
    error: str | None = None

    # The id of the benchmark that was run
    benchmark_id: int

    # The id of the function benchmarked
    function_id: int

    # Result data as a dictionary instead of _ModalGenericResult
    result: Dict[str, Any] | None = None
