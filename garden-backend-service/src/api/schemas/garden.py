from datetime import datetime
from pydantic import Field

from .base import BaseSchema, UniqueList
from .entrypoint import EntrypointMetadata


class GardenMetadata(BaseSchema):
    title: str
    authors: UniqueList[str] = Field(default_factory=list)
    contributors: UniqueList[str] = Field(default_factory=list)
    doi: str
    doi_is_draft: bool = True
    description: str | None
    publisher: str = "Garden-AI"
    year: str = Field(default_factory=lambda: str(datetime.now().year))
    language: str = "en"
    tags: UniqueList[str] = Field(default_factory=list)
    version: str = "0.0.1"
    entrypoint_ids: UniqueList[str] = Field(default_factory=list)
    entrypoint_aliases: dict[str, str] = Field(default_factory=dict)


class GardenCreateRequest(GardenMetadata):
    pass


class GardenMetadataResponse(GardenMetadata):
    id: int
    entrypoints: list[EntrypointMetadata] = Field(default_factory=list)
