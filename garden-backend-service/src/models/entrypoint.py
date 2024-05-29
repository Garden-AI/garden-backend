from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import ForeignKey, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.author import Author
    from src.models.tag import Tag
    from src.models.related_metadata import (
        DatasetMetadata,
        ModelMetadata,
        PaperMetadata,
        RepositoryMetadata,
    )

else:
    DatasetMetadata = "DatasetMetadata"
    ModelMetadata = "ModelMetadata"
    PaperMetadata = "PaperMetadata"
    RepositoryMetadata = "RepositoryMetadata"
    Author = "Author"
    Tag = "Tag"


class Entrypoint(Base):
    __tablename__ = "entrypoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    doi: Mapped[str] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool]
    title: Mapped[str]
    description: Mapped[str | None]
    year: Mapped[str]
    func_uuid: Mapped[UUID] = mapped_column(unique=True)
    container_uuid: Mapped[UUID] = mapped_column(unique=True)
    base_image_uri: Mapped[str]
    full_image_uri: Mapped[str]
    notebook_url: Mapped[str]

    short_name: Mapped[str]
    function_text: Mapped[str] = mapped_column(UnicodeText)

    authors: Mapped[List[Author]] = relationship(back_populates="entrypoint")
    tags: Mapped[List[Tag]] = relationship(back_populates="entrypoint")
    models: Mapped[List[ModelMetadata]] = relationship(back_populates="entrypoint")
    repositories: Mapped[List[RepositoryMetadata]] = relationship(
        back_populates="entrypoint"
    )
    papers: Mapped[List[PaperMetadata]] = relationship(back_populates="entrypoint")
    datasets: Mapped[List[DatasetMetadata]] = relationship(back_populates="entrypoint")

    test_functions: Mapped[List["TestFunction"]] = relationship(
        cascade="all, delete-orphan", back_populates="entrypoint"
    )


class TestFunction(Base):
    __tablename__ = "test_functions"
    id: Mapped[int] = mapped_column(primary_key=True)
    function_text: Mapped[str] = mapped_column(UnicodeText)

    entrypoint_id = mapped_column(ForeignKey("entrypoints.id"))
    entrypoint: Mapped[Entrypoint] = relationship(back_populates="test_functions")
