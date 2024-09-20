import base64

from pydantic import validator

from ..base import BaseSchema


class _ModalGenericResult(BaseSchema):
    # duplicates key fields from modal's protobuf api_pb2.GenericResult type, so our sdk can
    # build one manually and leave the rest of the result processing to modal
    status: int
    exception: str = ""
    traceback: str = ""
    serialized_tb: str = ""
    tb_line_cache: str = ""
    data: str = ""
    data_blob_id: str = ""

    @validator("serialized_tb", "tb_line_cache", "data", pre=True)
    def encode_bytes(cls, v):
        if isinstance(v, bytes):
            return base64.b64encode(v).decode()
        return v


class ModalInvocationRequest(BaseSchema):
    app_name: str
    function_name: str
    args_kwargs_serialized: bytes

    @validator("args_kwargs_serialized", pre=True)
    def decode_base64(cls, v):
        if isinstance(v, str):
            return base64.b64decode(v)
        return v


class ModalInvocationResponse(BaseSchema):
    result: _ModalGenericResult
    data_format: int
