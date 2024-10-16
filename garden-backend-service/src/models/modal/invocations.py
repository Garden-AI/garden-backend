#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ModalInvocation(Base):
    __tablename__ = "modal_invocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    function_id: Mapped[int] = mapped_column(ForeignKey("modal_functions.id"))
    date_invoked: Mapped[datetime.datetime] = mapped_column(
        DateTime(), server_default=func.now()
    )
    execution_time_seconds: Mapped[float]
    estimated_usage: Mapped[float]
