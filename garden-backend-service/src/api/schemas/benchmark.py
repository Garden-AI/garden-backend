from datetime import datetime
from typing import Any

from src.api.schemas.base import BaseSchema


class BenchmarkResultCreate(BaseSchema):
    benchmark_name: str
    benchmark_task_name: str
    metrics: dict[str, Any]


class BenchmarkResultResponse(BenchmarkResultCreate):
    id: int
    timestamp: datetime
