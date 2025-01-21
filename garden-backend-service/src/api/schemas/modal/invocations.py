from enum import Enum

from pydantic import model_validator

from src.modal.status import AsyncModalJobStatus

from ..base import B64Bytes, BaseSchema


class _ModalGenericResult(BaseSchema):
    # duplicates key fields from modal's protobuf api_pb2.GenericResult type, so our sdk can
    # build one manually and leave the rest of the result processing to modal
    status: int
    exception: str = ""
    traceback: str = ""
    serialized_tb: B64Bytes = b""
    tb_line_cache: B64Bytes = b""
    data: B64Bytes | None = b""
    # NOTE: this differs from the protobuf spec in that we send the full data_blob_url to
    # the garden client instead of data_blob_id (need active modal credentials to
    # request the presigned url)
    data_blob_url: str | None = None

    @model_validator(mode="after")
    def one_of_data_or_blob_url(self):
        assert (
            self.data or self.data_blob_url
        ), "At least one of data or data_blob_url should be set."
        return self


class ModalInvocationRequest(BaseSchema):
    function_id: int
    args_kwargs_serialized: B64Bytes | None = None
    args_blob_id: str | None = None

    @model_validator(mode="after")
    def one_of_data_or_blob_url(self):
        assert (
            self.args_kwargs_serialized or self.args_blob_id
        ), "At least one of args_kwargs_serialized or args_blob_id should be set."
        return self


class ModalInvocationResponse(BaseSchema):
    data_format: int
    result: _ModalGenericResult


class AsyncModalInvocationResponse(BaseSchema):
    id: int
    status: str


class ModalInvocationOutputsResponse(BaseSchema):
    id: int
    status: AsyncModalJobStatus
    result: _ModalGenericResult | None = None
    error: str | None = None


class ModalBlobUploadURLRequest(BaseSchema):
    content_length: int
    content_md5: str
    content_sha256_base64: str


class _UploadType(str, Enum):
    SINGLE = "single"
    MULTIPART = "multipart"


class _MultiPartUpload(BaseSchema):
    part_length: int
    upload_urls: list[str]
    completion_url: str


class ModalBlobUploadURLResponse(BaseSchema):
    # imitating the modal BlobCreate response payload
    blob_id: str
    upload_type: _UploadType

    upload_url: str | None = None
    multipart: _MultiPartUpload | None = None
