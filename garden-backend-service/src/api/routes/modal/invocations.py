import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from modal_proto import api_pb2
from sqlalchemy.ext.asyncio import AsyncSession

import modal
import modal._functions
from modal._resolver import Resolver
from modal._utils.grpc_utils import retry_transient_errors
from src.api.dependencies.auth import (
    authed_user,
    under_modal_usage_limit,
)
from src.api.dependencies.database import get_db_session
from src.api.dependencies.modal import get_modal_client
from src.api.schemas.modal.invocations import (
    AsyncModalInvocationResponse,
    ModalBlobUploadURLRequest,
    ModalBlobUploadURLResponse,
    ModalInvocationOutputsResponse,
    ModalInvocationRequest,
    _ModalGenericResult,
    _MultiPartUpload,
    _UploadType,
)
from src.config import Settings, get_settings
from src.modal.status import AsyncModalJobStatus
from src.modal.utils import monitor_modal_invocation
from src.models.modal.invocations import ModalInvocationLog, ModalInvocationResult
from src.models.modal.modal_function import ModalFunction
from src.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/modal-invocations")


@router.post(
    "/blob-uploads",
)
async def make_blob_upload_url(
    body: ModalBlobUploadURLRequest,
    modal_client: modal.Client = Depends(get_modal_client),
    settings: Settings = Depends(get_settings),
    _under_modal_usage_limit: bool = Depends(under_modal_usage_limit),
):
    """Get pre-signed URLs for uploading blobs to Modal's blob storage.

    This proxies the Modal BlobCreate RPC to get upload URLs that the Garden SDK
    can use directly to upload large arguments to Modal's blob storage.
    """

    # Forward the request to Modal
    request = api_pb2.BlobCreateRequest(
        content_md5=body.content_md5,
        content_sha256_base64=body.content_sha256_base64,
        content_length=body.content_length,
    )

    response = await retry_transient_errors(modal_client.stub.BlobCreate, request)

    if response.WhichOneof("upload_type_oneof") == "multipart":
        return ModalBlobUploadURLResponse(
            blob_id=response.blob_id,
            upload_type=_UploadType.MULTIPART,
            multipart=_MultiPartUpload(
                part_length=response.multipart.part_length,
                upload_urls=list(response.multipart.upload_urls),
                completion_url=response.multipart.completion_url,
            ),
        )
    else:
        return ModalBlobUploadURLResponse(
            blob_id=response.blob_id,
            upload_type=_UploadType.SINGLE,
            upload_url=response.upload_url,
        )


@router.post("/async")
async def invoke_modal_fn_async(
    body: ModalInvocationRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    modal_client: modal.Client = Depends(get_modal_client),
    under_modal_usage_limit: bool = Depends(under_modal_usage_limit),
    db: AsyncSession = Depends(get_db_session),
):
    # Fetch function from the database
    modal_fn: ModalFunction | None = await ModalFunction.get(db, id=body.function_id)
    if modal_fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Modal Function with id {body.function_id} found.",
        )

    app_name = modal_fn.modal_app.app_name
    function_name = modal_fn.function_name
    log = logger.bind(app_name=app_name, function_name=function_name)

    # Fetch the function from modal
    log.info("Fetching function object from modal")

    function = await _fetch_modal_function(modal_client, modal_fn, settings)

    # Create the _Invocation object
    log.info("Requesting invocation with modal")
    # If this is a class method, we need to specify the method name
    method_name = ""
    if "." in modal_fn.function_name:
        _, method_name = modal_fn.function_name.split(".")

    if body.args_blob_id is not None:
        invocation = await _create_invocation(
            function,
            modal_client,
            method_name=method_name,
            args_blob_id=body.args_blob_id,
        )
    else:
        assert body.args_kwargs_serialized
        invocation = await _create_invocation(
            function,
            modal_client,
            method_name=method_name,
            args_kwargs_serialized=body.args_kwargs_serialized,
        )

    # Log the invocation in the database
    db_log = ModalInvocationLog(
        user_id=user.id,
        function_id=modal_fn.id,
    )
    db.add(db_log)

    db_result = ModalInvocationResult(
        function_id=modal_fn.id,
        function_call_id=invocation.function_call_id,
        status=AsyncModalJobStatus.PENDING,
        log_id=db_log.id,
    )
    db.add(db_result)
    await db.commit()

    # Add monitoring to background tasks
    background_tasks.add_task(
        monitor_modal_invocation, invocation, db_result, modal_client, settings
    )

    # Return the invocation ID immediately
    return AsyncModalInvocationResponse(
        id=db_result.id,
        status=AsyncModalJobStatus.PENDING.value,
    )


@router.get("/{id}", response_model=ModalInvocationOutputsResponse)
async def get_modal_invocation_output(
    id: int,
    modal_client: modal.Client = Depends(get_modal_client),
    db: AsyncSession = Depends(get_db_session),
):
    inv = await ModalInvocationResult.get(db, id=id)
    if inv is None:
        return JSONResponse(
            status_code=404, content=f"Invocation with id: {id} not found."
        )

    response_data = {
        "id": id,
        "status": inv.status,
    }

    if inv.status is AsyncModalJobStatus.DONE and inv.output:
        parsed_output = api_pb2.FunctionGetOutputsItem.FromString(inv.output)
        modal_result = parsed_output.result
        modal_result_data = {
            "status": modal_result.status,
            "exception": modal_result.exception,
            "traceback": modal_result.traceback,
            "serialized_tb": modal_result.serialized_tb,
            "tb_line_cache": modal_result.tb_line_cache,
        }
        # handle either inline data or blob references
        if modal_result.HasField("data"):
            modal_result_data["data"] = parsed_output.result.data
        elif modal_result.HasField("data_blob_id"):
            modal_result_data["data_blob_url"] = await _get_blob_download_url(
                modal_client, modal_result.data_blob_id
            )

        response_data["result"] = _ModalGenericResult(**modal_result_data)
        logger.info(response_data=response_data)

    elif inv.status in {AsyncModalJobStatus.ERROR, AsyncModalJobStatus.TIMED_OUT}:
        response_data["error"] = inv.error

    logger.info(response_data=response_data)
    return response_data


async def _get_blob_download_url(client: modal.Client, blob_id: str) -> str:
    response: api_pb2.BlobGetResponse = await retry_transient_errors(
        client.stub.BlobGet, api_pb2.BlobGetRequest(blob_id=blob_id)
    )
    return response.download_url


async def _fetch_modal_function(
    client: modal.Client,
    fn_data: ModalFunction,
    settings: Settings,
) -> modal._functions._Function:
    resolver = Resolver(client=client)  # needed to hydrate objects eagerly
    if "." in fn_data.function_name:
        # if function belongs to a class, we need to instantiate a hydrated instance of the class to get at the _Function object
        cls_name, method_name = fn_data.function_name.split(".")
        cls = modal.cls._Cls.from_name(
            fn_data.modal_app.app_name,
            cls_name,
            environment_name=settings.MODAL_ENV,
        )
        obj = cls()
        function_obj = getattr(obj, method_name)
        await resolver.load(function_obj)
        return function_obj
    else:
        # else we need to hydrate a function we looked up by name
        obj = modal._functions._Function.from_name(
            fn_data.modal_app.app_name,
            fn_data.function_name,
            environment_name=settings.MODAL_ENV,
        )
        await resolver.load(obj)
        return obj


async def _create_invocation(
    function: modal.Function,
    client: modal.Client,
    invocation_type=api_pb2.FUNCTION_CALL_INVOCATION_TYPE_SYNC_LEGACY,
    args_kwargs_serialized: bytes = b"",
    args_blob_id: str | None = None,
    method_name="",
) -> modal._functions._Invocation:
    function_id = function.object_id
    # build the input payload with pre-serialized args (or blob ID)
    if args_blob_id is not None:
        inputs_item = api_pb2.FunctionPutInputsItem(
            input=api_pb2.FunctionInput(
                args_blob_id=args_blob_id,
                data_format=api_pb2.DATA_FORMAT_PICKLE,
                method_name=method_name,
            ),
            idx=0,
        )
    else:
        inputs_item = api_pb2.FunctionPutInputsItem(
            input=api_pb2.FunctionInput(
                args=args_kwargs_serialized,
                data_format=api_pb2.DATA_FORMAT_PICKLE,
                method_name=method_name,
            ),
            idx=0,
        )

    map_request = api_pb2.FunctionMapRequest(
        function_id=function_id,
        parent_input_id="",
        function_call_type=api_pb2.FUNCTION_CALL_TYPE_UNARY,
        pipelined_inputs=[inputs_item],
        function_call_invocation_type=invocation_type,
        # see: https://github.com/modal-labs/modal-client/blob/9507909d066785591b1d4f79f76b9e3ec4a07a33/modal/functions.py#L1208
    )

    logger.debug("sending FunctionMap request", map_request=map_request)
    # First request is necessary to get the function_call_id
    map_response = await retry_transient_errors(client.stub.FunctionMap, map_request)
    function_call_id = map_response.function_call_id
    logger.debug("received FunctionMap RPC response", map_response=map_response)

    if map_response.pipelined_inputs:
        return modal._functions._Invocation(client.stub, function_call_id, client)

    # second request seems to be primarily for error handling, but might as well stay consistent
    inputs_request = api_pb2.FunctionPutInputsRequest(
        function_id=function_id, inputs=[inputs_item], function_call_id=function_call_id
    )
    inputs_response = await retry_transient_errors(
        client.stub.FunctionPutInputs, inputs_request
    )
    processed_inputs = inputs_response.inputs
    if not processed_inputs:
        raise Exception(
            "Could not create function call - the input queue seems to be full"
        )
    return modal._functions._Invocation(client.stub, function_call_id, client)
