from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models._associations import gardens_entrypoints
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint

else:
    Entrypoint = "Entrypoint"


class Garden(Base):
    __tablename__ = "gardens"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    doi: Mapped[str] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool] = mapped_column(default=True)
    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    contributors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    description: Mapped[str | None]
    publisher: Mapped[str]
    year: Mapped[str]
    language: Mapped[str]
    version: Mapped[str]
    entrypoint_aliases: Mapped[dict[str, str]] = mapped_column(postgresql.JSON)

    # no back_populates; entrypoints don't directly point back to gardens
    entrypoints: Mapped[list[Entrypoint]] = relationship(
        Entrypoint,
        secondary=gardens_entrypoints,
        lazy="selectin",
    )
