from uuid import UUID

from pydantic import AliasPath, Field

from .base import Url
from .shared_function_schemas import CommonFunctionMetadata, CommonFunctionPatchRequest


class EntrypointMetadata(CommonFunctionMetadata):
    # Entrypoints always have a DOI
    # They can be in draft or published state
    doi: str
    doi_is_draft: bool

    # Metadata specific to Globus Compute functions
    func_uuid: UUID
    container_uuid: UUID
    base_image_uri: str
    full_image_uri: str
    notebook_url: Url

    # The function name is stored as "short_name" for entrypoints
    short_name: str | None = None


class EntrypointCreateRequest(EntrypointMetadata):
    owner_identity_id: UUID | None = None


class EntrypointMetadataResponse(EntrypointMetadata):
    owner_identity_id: UUID = Field(alias=AliasPath("owner", "identity_id"))
    id: int


class EntrypointPatchRequest(CommonFunctionPatchRequest):
    doi_is_draft: bool | None = None

    func_uuid: UUID | None = None
    container_uuid: UUID | None = None
    base_image_uri: str | None = None
    full_image_uri: str | None = None
    notebook_url: Url | None = None
