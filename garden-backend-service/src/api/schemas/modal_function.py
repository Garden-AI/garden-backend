from uuid import UUID

from pydantic import AliasPath, Field

from .base import BaseSchema, UniqueList, Url


class ModalFunctionMetadata(BaseSchema):
    # Identifiers
    doi: str | None

    # DataCite Metadata
    title: str
    description: str | None
    year: str

    # Function Metadata
    is_archived: bool = False
    function_name: str


class ModalFunctionMetadataResponse(ModalFunctionMetadata):
    id: UUID
    parent_app_name: str
    parent_app_id: UUID
