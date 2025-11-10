from pydantic import Field

from .base import BaseRelatedMetadataSchema, BaseSchema, UniqueList, Url


class _RepositoryMetadata(BaseRelatedMetadataSchema):
    repo_name: str
    url: Url
    contributors: UniqueList[str] = Field(default_factory=list)


class _PaperMetadata(BaseRelatedMetadataSchema):
    title: str | None = None
    authors: UniqueList[str] = Field(default_factory=list)
    doi: str | None = None
    description: str | None = None
    citation: str | None = None
    url: Url | None = None


class _DatasetMetadata(BaseRelatedMetadataSchema):
    title: str = Field(...)
    doi: str | None
    url: Url
    data_type: str | None
    repository: str


# protected_namespaces=() to allow model_* attribute names
class _ModelMetadata(BaseRelatedMetadataSchema, protected_namespaces=()):
    model_identifier: str
    model_repository: str
    model_version: str | None


class _NotebookMetadata(BaseRelatedMetadataSchema):
    title: str
    description: str | None
    url: Url


class CommonFunctionMetadataBase(BaseSchema):
    is_archived: bool = False

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
    notebooks: list[_NotebookMetadata] = Field(default_factory=list)


class CommonFunctionMetadata(CommonFunctionMetadataBase):
    function_text: str


class CommonFunctionMetadataSearchResult(CommonFunctionMetadataBase):
    pass


class CommonFunctionPatchRequest(BaseSchema):
    is_archived: bool | None = None

    title: str | None = None
    description: str | None = None
    year: str | None = None

    function_text: str | None = None
    example_usage: str | None = None

    authors: UniqueList[str] | None = None
    tags: UniqueList[str] | None = None
    test_functions: list[str] | None = None
    requirements: list[str] | None = None

    models: list[_ModelMetadata] | None = None
    repositories: list[_RepositoryMetadata] | None = None
    papers: list[_PaperMetadata] | None = None
    datasets: list[_DatasetMetadata] | None = None
    notebooks: list[_NotebookMetadata] | None = None
