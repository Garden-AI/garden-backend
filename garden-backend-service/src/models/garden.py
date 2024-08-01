from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models._associations import gardens_entrypoints
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
    from src.models.user import User

else:
    Entrypoint = "Entrypoint"
    User = "User"


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
    is_archived: Mapped[bool] = mapped_column(default=False)

    # no back_populates; entrypoints don't directly point back to gardens
    entrypoints: Mapped[list[Entrypoint]] = relationship(
        Entrypoint,
        secondary=gardens_entrypoints,
        lazy="selectin",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")
