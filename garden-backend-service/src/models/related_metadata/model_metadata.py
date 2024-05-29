from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
else:
    Entrypoint = "Entrypoint"


class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_identifier: Mapped[str]
    model_repository: Mapped[str]
    model_version: Mapped[str | None]

    entrypoint_id: Mapped[int] = mapped_column(ForeignKey("entrypoints.id"))
    entrypoint: Mapped[Entrypoint] = relationship(back_propagates="models")
