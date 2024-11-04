#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class InvocationStatus(enum.Enum):
    PENDING = "pending"
    ERROR = "error"
    DONE = "done"
    TIMED_OUT = "timed_out"


class ModalInvocation(Base):
    __tablename__ = "modal_invocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    function_id: Mapped[int] = mapped_column(ForeignKey("modal_functions.id"))
    function_call_id: Mapped[str]
    date_invoked: Mapped[datetime.datetime] = mapped_column(
        DateTime(), server_default=func.now()
    )
    date_resolved: Mapped[datetime.datetime] = mapped_column(nullable=True)
    estimated_usage: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[InvocationStatus] = mapped_column(default=InvocationStatus.PENDING)
    error: Mapped[str] = mapped_column(nullable=True)
    output: Mapped[bytes] = mapped_column(nullable=True)
