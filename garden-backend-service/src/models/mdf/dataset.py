from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models._associations import entrypoints_mdf_datasets
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
    from src.models.user import User
else:
    User = "User"
    Entrypoint = "Entrypoint"


class Dataset(Base):
    __tablename__ = "mdf_datasets"
    id: Mapped[int] = mapped_column(primary_key=True)

    doi: Mapped[str] = mapped_column(unique=True)
    versioned_source_id: Mapped[str] = mapped_column(unique=True)
    source_name: Mapped[str]
    version: Mapped[str]

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    flow_action_id: Mapped[UUID] = mapped_column(unique=True)

    previous_versions: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    connected_entrypoints: Mapped[list[Entrypoint]] = relationship(
        Entrypoint,
        secondary=entrypoints_mdf_datasets,
        back_populates="connected_mdf_datasets",
        lazy="selectin",
        cascade="all",
    )
