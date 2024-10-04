from datetime import datetime
from uuid import UUID

from pydantic import AliasPath, Field, computed_field

from .base import BaseSchema, UniqueList
from .entrypoint import EntrypointMetadataResponse
from .modal.modal_function import ModalFunctionMetadataResponse


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
    is_archived: bool = False


class GardenCreateRequest(GardenMetadata):
    entrypoint_ids: UniqueList[str] = Field(default_factory=list)
    modal_function_ids: UniqueList[int] = Field(default_factory=list)
    owner_identity_id: UUID | None = None


class GardenMetadataResponse(GardenMetadata):
    owner_identity_id: UUID = Field(alias=AliasPath("owner", "identity_id"))
    id: int
    entrypoints: list[EntrypointMetadataResponse] = Field(default_factory=list)
    modal_functions: list[ModalFunctionMetadataResponse] = Field(default_factory=list)

    @computed_field
    @property
    def entrypoint_ids(self) -> list[str]:
        return [ep.doi for ep in self.entrypoints]

    @computed_field
    @property
    def modal_function_ids(self) -> list[str]:
        return [mf.id for mf in self.modal_functions]


class GardenPatchRequest(BaseSchema):
    title: str | None = None
    authors: UniqueList[str] | None = None
    contributors: UniqueList[str] | None = None
    doi_is_draft: bool | None = None
    description: str | None = None
    publisher: str | None = None
    year: str | None = None
    language: str | None = None
    tags: UniqueList[str] | None = None
    version: str | None = None
    entrypoint_aliases: dict[str, str] = None
    is_archived: bool | None = None
    entrypoint_ids: UniqueList[str] | None = None
