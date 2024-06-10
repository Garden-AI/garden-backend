from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
else:
    Entrypoint = "Entrypoint"


class PaperMetadata(Base):
    __tablename__ = "paper_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    doi: Mapped[str]
    citation: Mapped[str | None]

    entrypoint_id: Mapped[int] = mapped_column(ForeignKey("entrypoints.id"))
    entrypoint: Mapped[Entrypoint] = relationship(back_populates="papers")
