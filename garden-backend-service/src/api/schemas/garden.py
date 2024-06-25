from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import BaseSchema, UniqueList
from .entrypoint import EntrypointMetadata


class GardenMetadata(BaseSchema):
    title: str
    authors: UniqueList[str] = Field(default_factory=list)
    contributors: UniqueList[str] = Field(default_factory=list)
    doi: str
    doi_is_draft: bool | None = None
    description: str | None
    publisher: str = "Garden-AI"
    year: str = Field(default_factory=lambda: str(datetime.now().year))
    language: str = "en"
    tags: UniqueList[str] = Field(default_factory=list)
    version: str = "0.0.1"
    entrypoint_aliases: dict[str, str] = Field(default_factory=dict)


class GardenCreateRequest(GardenMetadata):
    entrypoint_ids: UniqueList[str] = Field(default_factory=list)
    owner_identity_id: UUID | None = None


class GardenMetadataResponse(GardenMetadata):
    id: int
    entrypoints: list[EntrypointMetadata] = Field(default_factory=list)
