#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.modal.status import AsyncModalJobStatus
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.modal.modal_function import ModalFunction
    from src.models.user import User
else:
    ModalFunction = "ModalFunction"
    User = "User"


class ModalInvocationLog(Base):
    """Tracks invocation history and usage for analytics purposes."""

    __tablename__ = "modal_invocation_logs"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Non-nullable so we can calculate usage per-user even if function is deleted
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")

    # Nullable since we want to keep logs even if function is deleted
    function_id: Mapped[int | None] = mapped_column(
        ForeignKey("modal_functions.id", ondelete="SET NULL"), nullable=True
    )
    function: Mapped["ModalFunction | None"] = relationship(
        lazy="selectin", uselist=False
    )

    date_invoked: Mapped[datetime.datetime] = mapped_column(
        DateTime(), server_default=func.now()
    )
    date_resolved: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    estimated_usage: Mapped[float] = mapped_column(default=0.0)

    # One-to-one relationship with results (nullable, keep logs if results are deleted)
    result: Mapped["ModalInvocationResult | None"] = relationship(
        "ModalInvocationResult",
        back_populates="log",
        uselist=False,
        lazy="selectin",
    )


class ModalInvocationResult(Base):
    """Stores the results of a modal function invocation."""

    __tablename__ = "modal_invocation_results"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Non-nullable since results should be deleted when function is deleted
    function_id: Mapped[int] = mapped_column(
        ForeignKey("modal_functions.id", ondelete="CASCADE")
    )
    function: Mapped[ModalFunction] = relationship(lazy="selectin")

    function_call_id: Mapped[str]
    status: Mapped[AsyncModalJobStatus] = mapped_column(
        default=AsyncModalJobStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(nullable=True)
    output: Mapped[bytes | None] = mapped_column(nullable=True)

    # One-to-one relationship with log (non-nullable)
    log_id: Mapped[int] = mapped_column(ForeignKey("modal_invocation_logs.id"))
    log: Mapped[ModalInvocationLog] = relationship(
        "ModalInvocationLog",
        back_populates="result",
        lazy="selectin",
        uselist=False,
    )
