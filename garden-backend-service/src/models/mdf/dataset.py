from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
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

    versioned_source_id: Mapped[str] = mapped_column(unique=True)
    doi: Mapped[str | None] = mapped_column(nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    previous_versions: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    connected_entrypoints: Mapped[list[Entrypoint]] = relationship(
        Entrypoint,
        secondary=entrypoints_mdf_datasets,
        back_populates="connected_mdf_datasets",
        lazy="selectin",
        cascade="save-update, merge, refresh-expire, expunge",
    )

    # Some old MDF datasets don't have a DOI
    __table_args__ = (
        Index(
            "not_null_doi_is_unique",
            "doi",
            unique=True,
            sqlite_where=("doi IS NOT NULL"),
        ),
    )

    def get_accelerate_metadata(self):
        return {
            "owner_identity_id": str(self.owner.identity_id),
            "previous_versions": self.previous_versions,
            "connected_entrypoints": [
                connected_entrypoint.doi
                for connected_entrypoint in self.connected_entrypoints
            ],
        }
