from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class BenchmarkResult(Base):
    """Stores benchmark metrics/results."""

    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(primary_key=True)

    benchmark_name: Mapped[str] = mapped_column(String, nullable=False)

    benchmark_task_name: Mapped[str] = mapped_column(String, nullable=False)

    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
