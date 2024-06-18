"""Pydantic schemas equivalent to their counterparts in the garden-ai sdk, as of v1.0.10"""
import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.api.schemas.base import UniqueList


class _Repository(BaseModel):
    repo_name: str = Field(...)
    url: str = Field(...)
    contributors: List[str] = Field(default_factory=list)


class _Paper(BaseModel):
    title: str = Field(...)
    authors: List[str] = Field(default_factory=list)
    doi: Optional[str] = Field(None)
    citation: Optional[str] = Field(None)


class _Step(BaseModel):
    function_name: str = Field(...)
    function_text: str = Field(...)
    description: Optional[str] = Field(None)


class _DatasetConnection(BaseModel):
    title: str = Field(...)
    doi: Optional[str] = Field(None)
    url: str = Field(...)
    data_type: Optional[str] = Field(None)
    repository: str = Field(...)


class _ModelMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_identifier: str = Field(...)
    model_repository: str = Field(...)
    model_version: Optional[str] = Field(None)
    datasets: List[_DatasetConnection] = Field(default_factory=list)


class _EntrypointMetadata(BaseModel):
    doi: Optional[str] = Field(None)
    title: str = Field(...)
    authors: List[str] = Field(...)
    short_name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    year: str = Field(default_factory=lambda: str(datetime.now().year))
    tags: UniqueList[str] = Field(default_factory=list)
    models: List[_ModelMetadata] = Field(default_factory=list)
    repositories: List[_Repository] = Field(default_factory=list)
    papers: List[_Paper] = Field(default_factory=list)
    datasets: List[_DatasetConnection] = Field(default_factory=list)
    # The PrivateAttrs below are used internally for publishing.
    # _test_functions: List[str] = PrivateAttr(default_factory=list)
    # _target_garden_doi: Optional[str] = PrivateAttr(None)
    # _as_step: Optional[_Step] = PrivateAttr(None)


class _RegisteredEntrypoint(_EntrypointMetadata):
    doi: str = Field(
        ...
    )  # Repeating this field from base class because DOI is mandatory for RegisteredEntrypoint
    doi_is_draft: bool = Field(True)
    func_uuid: UUID = Field(...)
    container_uuid: UUID = Field(...)
    base_image_uri: Optional[str] = Field(None)
    full_image_uri: Optional[str] = Field(None)
    notebook_url: Optional[str] = Field(None)
    steps: List[_Step] = Field(default_factory=list)
    test_functions: List[str] = Field(default_factory=list)


class _PublishedGarden(BaseModel):
    title: str = Field(...)
    authors: List[str] = Field(...)
    contributors: UniqueList
    doi: str = Field(...)
    description: Optional[str] = Field(None)
    publisher: str = "Garden-AI"
    year: str = Field(default_factory=lambda: str(datetime.now().year))
    language: str = "en"
    tags: UniqueList
    version: str = "0.0.1"
    entrypoints: List[_RegisteredEntrypoint] = Field(...)
    entrypoint_aliases: Dict[str, str] = Field(default_factory=dict)
