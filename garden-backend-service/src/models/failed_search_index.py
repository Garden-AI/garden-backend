from datetime import datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class FailedSearchIndexUpdate(Base):
    __tablename__ = "failed_search_index_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    doi: Mapped[str | None]
    operation_type: Mapped[str | None]
    error_message: Mapped[str | None]
    retry_count: Mapped[int] = mapped_column(default=0)
    last_attempt: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP, default=datetime.utcnow
    )
