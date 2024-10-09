from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from src.models._associations import entrypoints_mdf_datasets
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.garden import Garden
    from src.models.mdf.dataset import Dataset
    from src.models.user import User
else:
    Garden = "Garden"
    User = "User"
    Dataset = "Dataset"


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
    is_archived: Mapped[bool] = mapped_column(default=False)

    short_name: Mapped[str]
    function_text: Mapped[str]

    authors: Mapped[list[str]] = mapped_column(ARRAY(String))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String))
    test_functions: Mapped[list[str]] = mapped_column(ARRAY(String))
    requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # NOTE: modifications to these lists / dictionaries won't be picked up
    # by sqlalchemy ORM. Updates should replace with a copy.
    models: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    repositories: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    papers: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    datasets: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    connected_mdf_datasets: Mapped[list[Dataset]] = relationship(
        Dataset,
        secondary=entrypoints_mdf_datasets,
        back_populates="connected_entrypoints",
        lazy="selectin",
        cascade="save-update, merge, refresh-expire, expunge",
    )
