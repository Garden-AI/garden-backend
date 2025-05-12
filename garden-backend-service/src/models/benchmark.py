from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base
from src.models.modal.invocations import ModalInvocationResult
from src.models.modal.modal_function import ModalFunction


class Benchmark(Base):
    """Keeps track of available benchmarks"""

    __tablename__ = "benchmarks"
    id: Mapped[int] = mapped_column(primary_key=True)
    function_id: Mapped[int]


class BenchmarkRun(Base):
    """Stores information about benchmark runs"""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The benchmark function that was executed
    benchmark_id: Mapped[int] = mapped_column(ForeignKey(Benchmark.id))
    benchmark: Mapped[Benchmark] = relationship(
        "Benchmark", foreign_keys=[benchmark_id]
    )

    # The function that was benchmarked
    function_id: Mapped[int] = mapped_column(ForeignKey(ModalFunction.id))
    function: Mapped[ModalFunction] = relationship(
        "ModalFunction", foreign_keys=[function_id]
    )

    # The invocation result that contains the benchmark output
    invocation_id: Mapped[int] = mapped_column(
        ForeignKey(ModalInvocationResult.id, ondelete="CASCADE")
    )
    invocation: Mapped[ModalInvocationResult] = relationship("ModalInvocationResult")

    # Optional task ID for grouping benchmarks by task
    task_id: Mapped[int | None] = mapped_column(nullable=True)
