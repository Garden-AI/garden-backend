# from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base

# from src.models._associations import entrypoints_datasets

"""
if TYPE_CHECKING:
    from src.models.entrypoint import Entrypoint
else:
    Entrypoint = "Entrypoint"
"""


class Dataset(Base):
    __tablename__ = "mdf-datasets"
    id: Mapped[str] = mapped_column(primary_key=True)  # mdf SI subject id
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    flow_action_id: Mapped[str]

    doi: Mapped[str]
    source_id: Mapped[str]
    version: Mapped[str]

    previous_versions: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=[]
    )  # ids of all previous versions

    """
    connected_entrypoints: Mapped[list[Entrypoint]] = relationship(
        Entrypoint,
        secondary=entrypoints_datasets,
        back_populates='connected_datasets'
    )
    """
