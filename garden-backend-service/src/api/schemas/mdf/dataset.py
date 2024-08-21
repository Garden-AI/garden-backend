from uuid import UUID

from pydantic import Field, RootModel

from ..base import BaseSchema, UniqueList
from ..search.globus_search import GSearchResult, LegacyResult, ModernResult


class AccelerateDatasetMetadata(BaseSchema):
    owner_identity_id: UUID
    connected_entrypoints: UniqueList[str] = Field(default_factory=list)
    previous_versions: UniqueList[str] | None = Field(default=None)


class MDFModernResult(BaseSchema, ModernResult):
    accelerate_metadata: AccelerateDatasetMetadata | None = None


class MDFLegacyResult(BaseSchema, LegacyResult):
    accelerate_metadata: AccelerateDatasetMetadata | None = None


class MDFGMetaResult(BaseSchema, RootModel[MDFLegacyResult | MDFModernResult]):
    root: MDFLegacyResult | MDFModernResult


class MDFSearchResponse(BaseSchema, GSearchResult):
    gmeta: list[MDFGMetaResult] | None = None


class MDFDatasetCreateRequest(BaseSchema):
    flow_action_id: UUID
    versioned_source_id: str
    owner_identity_id: UUID
    previous_versions: UniqueList[str] = Field(default_factory=list)
