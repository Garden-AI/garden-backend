from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user import User
else:
    User = "User"


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

    flow_action_id: Mapped[str]

    previous_versions: Mapped[list[str] | None] = mapped_column(ARRAY(String))
