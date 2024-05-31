from ._types import UniqueList
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# Note: from_attributes=True allows instantiation from ORM model instances


class _RepositoryMetadata(BaseModel, from_attributes=True):
    repo_name: str
    url: HttpUrl
    contributors: UniqueList[str]


class _PaperMetadata(BaseModel, from_attributes=True):
    title: str
    authors: UniqueList[str]
    doi: str | None
    citation: str | None


class _DatasetMetadata(BaseModel, from_attributes=True):
    title: str = Field(...)
    doi: str | None
    url: HttpUrl
    data_type: str | None
    repository: str


# protected_namespaces=() to allow model_* attribute names
class _ModelMetadata(BaseModel, from_attributes=True, protected_namespaces=()):
    model_identifier: str
    model_repository: str
    model_version: str | None


class EntrypointMetadata(BaseModel):
    doi: str
    doi_is_draft: bool
    title: str
    description: str | None
    year: str
    func_uuid: UUID
    container_uuid: UUID
    base_image_uri: str
    full_image_uri: str
    notebook_url: HttpUrl

    short_name: str
    function_text: str

    authors: UniqueList[str]
    tags: UniqueList[str]
    test_functions: list[str]

    models: list[_ModelMetadata]
    repositories: list[_RepositoryMetadata]
    papers: list[_PaperMetadata]
    datasets: list[_DatasetMetadata]


class EntrypointCreateRequest(EntrypointMetadata):
    pass


class EntrypointMetadataResponse(EntrypointMetadata, from_attributes=True):
    id: int
