from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base
from src.models.modal.invocations import ModalInvocationResult
from src.models.modal.modal_function import ModalFunction


class Benchmark(Base):
    """Track available benchmarks"""

    __tablename__ = "benchmarks"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    tasks: Mapped[list["BenchmarkTask"]] = relationship(
        back_populates="benchmark", lazy="selectin"
    )


class BenchmarkTask(Base):
    """Track tasks associated with benchmarks"""

    __tablename__ = "benchmark_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)

    benchmark_id: Mapped[int] = mapped_column(ForeignKey(Benchmark.id))
    benchmark: Mapped["Benchmark"] = relationship(
        back_populates="tasks", lazy="selectin"
    )

    function_id: Mapped[int] = mapped_column(
        ForeignKey(ModalFunction.id, ondelete="SET NULL")
    )
    function: Mapped[ModalFunction] = relationship(lazy="selectin")


class BenchmarkRun(Base):
    """Stores information about benchmark runs"""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    benchmark_id: Mapped[int] = mapped_column(ForeignKey(Benchmark.id))
    benchmark: Mapped[Benchmark] = relationship(
        "Benchmark", foreign_keys=[benchmark_id]
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey(BenchmarkTask.id, ondelete="SET NULL")
    )
    task: Mapped[BenchmarkTask] = relationship()

    # The function that was benchmarked
    function_id: Mapped[int] = mapped_column(
        ForeignKey(ModalFunction.id, ondelete="SET NULL")
    )
    function: Mapped[ModalFunction] = relationship(
        "ModalFunction", foreign_keys=[function_id]
    )

    # The invocation result that contains the task output
    invocation_id: Mapped[int] = mapped_column(
        ForeignKey(ModalInvocationResult.id, ondelete="SET NULL")
    )
    invocation: Mapped[ModalInvocationResult] = relationship("ModalInvocationResult")

    date: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
