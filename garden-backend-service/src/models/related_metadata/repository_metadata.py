from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
else:
    Entrypoint = "Entrypoint"


class RepositoryMetadata(Base):
    __tablename__ = "repository_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    repo_name: Mapped[str]
    url: Mapped[str]
    contributors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))

    entrypoint_id: Mapped[int] = mapped_column(ForeignKey("entrypoints.id"))
    entrypoint: Mapped[Entrypoint] = relationship(back_populates="repositories")
