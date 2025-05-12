from datetime import datetime
from typing import Any, Dict

from pydantic import Base64Bytes

from src.api.schemas.base import BaseSchema
from src.api.schemas.modal.modal_function import ModalFunctionMetadataResponse
from src.modal.status import AsyncModalJobStatus


class BenchmarkRequest(BaseSchema):
    # The id of the benchmarking task to run, i.e. Benchmark: MatBecnch Discovery -> Task: IS2RE
    task_id: int
    # The id of the function to benchmark
    function_id: int

    args_kwargs_serialized: Base64Bytes | None = None
    args_blob_id: str | None = None


class BenchmarkResult(BaseSchema):
    # Status of the job
    status: AsyncModalJobStatus

    # Error message if any
    error: str | None = None

    # The id of the benchmark that was run
    benchmark_id: int

    # The id of the function benchmarked
    function_id: int

    # Date when the benchmark was invoked
    date_invoked: datetime | None = None

    # Result data as a dictionary instead of _ModalGenericResult
    result: Dict[str, Any] | None = None


class BenchmarkMetadata(ModalFunctionMetadataResponse):
    # For now benchmarks are no different from regular modal functions
    pass
