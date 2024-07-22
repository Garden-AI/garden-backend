from pydantic import Field

from .base import BaseSchema, UniqueList


class DatasetMetadata(BaseSchema):
    versioned_source_id: str

    doi: str
    source_id: str
    version: str

    previous_versions: UniqueList[str] = Field(default_factory=list)
