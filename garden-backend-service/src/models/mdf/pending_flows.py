from datetime import datetime
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class PendingMDFFlow(Base):
    __tablename__ = "pending_mdf_flows"
    id: Mapped[int] = mapped_column(primary_key=True)

    flow_action_id: Mapped[UUID] = mapped_column(unique=True)

    versioned_source_id: Mapped[str] = mapped_column(unique=True)
    owner_identity_id: Mapped[UUID]
    previous_versions: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    retry_count: Mapped[int] = mapped_column(default=0)
    last_attempt: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP, default=datetime.utcnow
    )
