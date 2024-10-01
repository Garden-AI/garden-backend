from ..base import B64Bytes, BaseSchema


class _ModalGenericResult(BaseSchema):
    # duplicates key fields from modal's protobuf api_pb2.GenericResult type, so our sdk can
    # build one manually and leave the rest of the result processing to modal
    status: int
    exception: str = ""
    traceback: str = ""
    serialized_tb: B64Bytes = b""
    tb_line_cache: B64Bytes = b""
    data: B64Bytes = b""
    data_blob_id: str = ""


class ModalInvocationRequest(BaseSchema):
    app_name: str
    function_name: str
    args_kwargs_serialized: B64Bytes


class ModalInvocationResponse(BaseSchema):
    result: _ModalGenericResult
    data_format: int
