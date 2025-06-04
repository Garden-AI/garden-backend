from uuid import UUID

from pydantic import AliasPath, Field

from ..shared_function_schemas import CommonFunctionMetadata, CommonFunctionPatchRequest


class ModalFunctionMetadata(CommonFunctionMetadata):
    # Equivalent to "short_name" on entrypoints
    function_name: str
    file_contents: str | None = None
    # Modal functions get a DOI when they are published
    # If they don't have a DOI, they are in draft state
    doi: str | None = None
    # modal supports conda requirements but entrypoints don't
    conda_requirements: list[str] = Field(default_factory=list)
    example_usage: str = ""


class ModalFunctionMetadataResponse(ModalFunctionMetadata):
    id: int = Field(..., description="The unique identifier for the modal function")
    modal_app_id: int
    owner: str = Field(validation_alias=AliasPath("owner", "name"))
    owner_identity_id: UUID = Field(validation_alias=AliasPath("owner", "identity_id"))
    hardware_spec: dict
    num_invocations: int = Field(
        default_factory=lambda: 0,
        description="The number of times this function has been invoked",
    )


class ModalFunctionPatchRequest(CommonFunctionPatchRequest):
    doi: str | None = None
    function_name: str | None = None
