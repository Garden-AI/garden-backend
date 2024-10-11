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


class CommonFunctionMetadata(BaseSchema):
    is_archived: bool = False

    function_text: str

    title: str
    description: str | None
    year: str

    authors: UniqueList[str] = Field(default_factory=list)
    tags: UniqueList[str] = Field(default_factory=list)
    test_functions: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)

    models: list[_ModelMetadata] = Field(default_factory=list)
    repositories: list[_RepositoryMetadata] = Field(default_factory=list)
    papers: list[_PaperMetadata] = Field(default_factory=list)
    datasets: list[_DatasetMetadata] = Field(default_factory=list)


class CommonFunctionPatchRequest(BaseSchema):
    is_archived: bool | None = None

    title: str | None = None
    description: str | None = None
    year: str | None = None

    function_text: str | None = None

    authors: UniqueList[str] | None = None
    tags: UniqueList[str] | None = None
    test_functions: list[str] | None = None
    requirements: list[str] | None = None

    models: list[_ModelMetadata] | None = None
    repositories: list[_RepositoryMetadata] | None = None
    papers: list[_PaperMetadata] | None = None
    datasets: list[_DatasetMetadata] | None = None
