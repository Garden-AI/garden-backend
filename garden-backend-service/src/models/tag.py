from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
else:
    Entrypoint = "Entrypoint"


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str]

    entrypoint_id: Mapped[int] = mapped_column(ForeignKey("entrypoints.id"))
    entrypoint: Mapped[Entrypoint] = relationship(back_propagates="tags")
