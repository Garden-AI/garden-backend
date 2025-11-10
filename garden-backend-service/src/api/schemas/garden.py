from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasPath, Field, computed_field

from src.models.garden import GardenState

from .base import BaseSchema, UniqueList
from .entrypoint import EntrypointMetadataResponse
from .hpc import HpcFunctionMetadataResponse
from .modal.modal_function import ModalFunctionMetadataResponse


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
    entrypoint_aliases: dict[str, str] = Field(default_factory=dict)
    is_archived: bool = False

    @computed_field
    @property
    def state(self) -> GardenState:
        return GardenState.determine_state(self)


class GardenCreateRequest(GardenMetadata):
    entrypoint_ids: UniqueList[str] = Field(default_factory=list)
    modal_function_ids: UniqueList[int] = Field(default_factory=list)
    hpc_function_ids: UniqueList[int] = Field(default_factory=list)
    owner_identity_id: UUID | None = None
    doi: str | None = None


class GardenMetadataResponse(GardenMetadata):
    owner: str = Field(validation_alias=AliasPath("owner", "name"))
    owner_identity_id: UUID = Field(validation_alias=AliasPath("owner", "identity_id"))
    id: int
    entrypoints: list[EntrypointMetadataResponse] = Field(default_factory=list)
    modal_functions: list[ModalFunctionMetadataResponse] = Field(default_factory=list)
    hpc_functions: list[HpcFunctionMetadataResponse] = Field(default_factory=list)
    marked_for_deletion: datetime | None

    @computed_field
    @property
    def entrypoint_ids(self) -> list[str]:
        return [ep.doi for ep in self.entrypoints]

    @computed_field
    @property
    def modal_function_ids(self) -> list[int]:
        return [mf.id for mf in self.modal_functions]

    @computed_field
    @property
    def hpc_function_ids(self) -> list[int]:
        return [hpcf.id for hpcf in self.hpc_functions]


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
    entrypoint_aliases: dict[str, str] | None = None
    is_archived: bool | None = None
    entrypoint_ids: UniqueList[str] | None = None
    modal_function_ids: UniqueList[int] | None = None
    hpc_function_ids: UniqueList[int] | None = None

    @computed_field
    @property
    def target_state(self) -> GardenState | None:
        """
        Determine the desired state change (if any) entailed by the request, or
        None if no state change is requested.

        Note that this is only responsible for determining the desired state
        change, not for validating that the transition is legal.
        """
        if self.is_archived is None and self.doi_is_draft is None:
            # no state change requested
            return None
        wants_archived = self.is_archived is True
        wants_published = self.doi_is_draft is False

        match (wants_archived, wants_published):
            case (True, True):
                # treat this as requesting an ARCHIVE transition since
                # is_archived=True and doi_is_draft=False is the final state of
                # an archived garden
                return GardenState.ARCHIVED
            case (True, False):
                # treat this as requesting a transition to ARCHIVED
                # since we can't return to a draft state
                return GardenState.ARCHIVED
            case (False, True):
                # unambiguously requesting a transition to PUBLISHED
                return GardenState.PUBLISHED
            case (False, False):
                # unlikely case: explicitly requesting a DRAFT state,
                # which is the default
                return GardenState.DRAFT


class GardenSearchFilter(BaseSchema):
    field_name: str
    values: list[str]
    operation: Literal["AND", "OR"] | None = Field(default="AND")


class GardenSearchFacets(BaseSchema):
    tags: dict[str, int] = Field(default_factory=dict)
    model_authors: dict[str, int] = Field(default_factory=dict)
    gardeners: dict[str, int] = Field(default_factory=dict)
    year: dict[str, int] = Field(default_factory=dict)
    function_type: dict[str, int] = Field(default_factory=dict)
    hpc_endpoint: dict[str, int] = Field(default_factory=dict)


class GardenSearchSort(BaseSchema):
    field_name: str
    order: str


class GardenSearchRequest(BaseSchema):
    q: str
    limit: int = 10
    offset: int = Field(
        0, ge=0, description="Offset for pagination (number of results to skip)"
    )
    filters: list[GardenSearchFilter] = Field(default_factory=list)
    sort: GardenSearchSort | None = None


class GardenSearchResponse(BaseSchema):
    count: int
    total: int
    offset: int
    garden_meta: list[GardenMetadataResponse]
    facets: GardenSearchFacets
