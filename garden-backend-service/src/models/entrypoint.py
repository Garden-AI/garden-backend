from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.garden import Garden
    from src.models.related_metadata import (
        DatasetMetadata,
        ModelMetadata,
        PaperMetadata,
        RepositoryMetadata,
    )
    from src.models.user import User

else:
    DatasetMetadata = "DatasetMetadata"
    ModelMetadata = "ModelMetadata"
    PaperMetadata = "PaperMetadata"
    RepositoryMetadata = "RepositoryMetadata"
    Garden = "Garden"
    User = "User"


class Entrypoint(Base):
    __tablename__ = "entrypoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    doi: Mapped[str] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool]
    title: Mapped[str]
    description: Mapped[str | None]
    year: Mapped[str]
    func_uuid: Mapped[UUID] = mapped_column(unique=True)
    container_uuid: Mapped[UUID]
    base_image_uri: Mapped[str]
    full_image_uri: Mapped[str]
    notebook_url: Mapped[str]

    short_name: Mapped[str]
    function_text: Mapped[str]

    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    test_functions: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))

    # lazy=selectin to load eagerly by default; cascade options are set to
    # everything but "refresh-expire" for asyncio reasons.
    # (see: https://docs.sqlalchemy.org/en/20/orm/cascades.html)
    models: Mapped[list[ModelMetadata]] = relationship(
        back_populates="entrypoint",
        lazy="selectin",
        cascade="save-update, merge, expunge, delete, delete-orphan",
    )
    repositories: Mapped[list[RepositoryMetadata]] = relationship(
        back_populates="entrypoint",
        lazy="selectin",
        cascade="save-update, merge, expunge, delete, delete-orphan",
    )
    papers: Mapped[list[PaperMetadata]] = relationship(
        back_populates="entrypoint",
        lazy="selectin",
        cascade="save-update, merge, expunge, delete, delete-orphan",
    )
    datasets: Mapped[list[DatasetMetadata]] = relationship(
        back_populates="entrypoint",
        lazy="selectin",
        cascade="save-update, merge, expunge, delete, delete-orphan",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")
