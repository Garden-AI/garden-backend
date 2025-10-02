from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from src.models._associations import (
    gardens_entrypoints,
    gardens_hpc_functions,
    gardens_modal_functions,
)
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
    from src.models.functions.hpc.hpc_functions import HpcFunction
    from src.models.functions.modal.modal_function import ModalFunction
    from src.models.user import User

else:
    Entrypoint = "Entrypoint"
    HpcFunction = "HpcFunction"
    ModalFunction = "ModalFunction"
    User = "User"


class GardenState(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def determine_state(cls, obj) -> GardenState:
        # helper for db model and schema's respective computed fields
        assert hasattr(obj, "is_archived") and hasattr(obj, "doi_is_draft")
        match (obj.is_archived, obj.doi_is_draft):
            case (True, _):
                # We shouldn't hit the case where self.is_archived is True and self.doi_is_draft is True,
                # but we'll count that "invalid" state as ARCHIVED rather than throwing an error.
                return cls.ARCHIVED
            case (False, True):
                return cls.DRAFT
            case (False, False):
                return cls.PUBLISHED
            case _:
                # unreachable
                raise ValueError("Could not determine state")


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

    # Modal Functions don't point back to gardens either
    modal_functions: Mapped[list[ModalFunction]] = relationship(
        ModalFunction,
        secondary=gardens_modal_functions,
        lazy="selectin",
    )

    hpc_functions: Mapped[list[HpcFunction]] = relationship(
        HpcFunction,
        secondary=gardens_hpc_functions,
        lazy="selectin",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    marked_for_deletion: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def state(self) -> GardenState:
        return GardenState.determine_state(self)
