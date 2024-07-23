from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


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
