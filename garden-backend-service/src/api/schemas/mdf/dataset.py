from pydantic import Field

from .base import BaseSchema, UniqueList


class MDFDatasetMetadata(BaseSchema):
    doi: str
    versioned_source_id: str
    source_name: str
    version: str

    previous_versions: UniqueList[str] = Field(default_factory=list)
