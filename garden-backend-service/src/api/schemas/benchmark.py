from datetime import datetime
from typing import Any, Dict

from src.api.schemas.base import BaseSchema
from src.api.schemas.modal.modal_function import ModalFunctionMetadataResponse
from src.modal.status import AsyncModalJobStatus


class BenchmarkRequest(BaseSchema):
    # The id of the function to benchmark
    function_id: int


class BenchmarkResult(BaseSchema):
    # Status of the job
    status: AsyncModalJobStatus

    # Error message if any
    error: str | None = None

    # The id of the benchmark that was run
    benchmark_id: int

    # The benchmark task
    task_id: int

    # The id of the function benchmarked
    function_id: int

    # Date when the benchmark was invoked
    date_invoked: datetime | None = None

    # Result data as a dictionary instead of _ModalGenericResult
    result: Dict[str, Any] | None = None


class BenchmarkTaskMetadata(BaseSchema):
    id: int
    function: ModalFunctionMetadataResponse


class BenchmarkMetadata(BaseSchema):
    id: int
    name: str
    description: str | None = None
    # tasks map to modal functions
    tasks: list[BenchmarkTaskMetadata]
