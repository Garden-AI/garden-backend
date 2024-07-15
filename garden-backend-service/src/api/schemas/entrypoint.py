from uuid import UUID

from pydantic import Field

from .base import BaseSchema, UniqueList, Url


class _RepositoryMetadata(BaseSchema):
    repo_name: str
    url: Url
    contributors: UniqueList[str] = Field(default_factory=list)


class _PaperMetadata(BaseSchema):
    title: str
    authors: UniqueList[str] = Field(default_factory=list)
    doi: str | None
    citation: str | None


class _DatasetMetadata(BaseSchema):
    title: str = Field(...)
    doi: str | None
    url: Url
    data_type: str | None
    repository: str


# protected_namespaces=() to allow model_* attribute names
class _ModelMetadata(BaseSchema, protected_namespaces=()):
    model_identifier: str
    model_repository: str
    model_version: str | None


class EntrypointMetadata(BaseSchema):
    doi: str
    doi_is_draft: bool
    title: str
    description: str | None
    year: str
    func_uuid: UUID
    container_uuid: UUID
    base_image_uri: str
    full_image_uri: str
    notebook_url: Url

    short_name: str
    function_text: str

    authors: UniqueList[str] = Field(default_factory=list)
    tags: UniqueList[str] = Field(default_factory=list)
    test_functions: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)

    models: list[_ModelMetadata] = Field(default_factory=list)
    repositories: list[_RepositoryMetadata] = Field(default_factory=list)
    papers: list[_PaperMetadata] = Field(default_factory=list)
    datasets: list[_DatasetMetadata] = Field(default_factory=list)


class EntrypointCreateRequest(EntrypointMetadata):
    owner_identity_id: UUID | None = None


class EntrypointMetadataResponse(EntrypointMetadata):
    owner_identity_id: UUID
    id: int
