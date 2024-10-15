import time

import modal
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from modal._utils.grpc_utils import retry_transient_errors
from modal_proto import api_pb2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import authed_user, modal_vip, under_modal_usage_limit
from src.api.dependencies.database import get_db_session
from src.api.dependencies.modal import get_modal_client
from src.api.schemas.modal.invocations import (
    ModalInvocationRequest,
    ModalInvocationResponse,
)
from src.config import Settings, get_settings
from src.models.modal.invocations import ModalInvocation
from src.models.modal.modal_function import ModalFunction
from src.models.user import User
from src.usage import estimate_usage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/modal-invocations")


# TODO: Remove me, just using for testing
@router.get("")
async def get_invocations(
    db: AsyncSession = Depends(get_db_session),
):
    invocations = await db.scalars(select(ModalInvocation))
    return invocations.all()


@router.post("", response_model=ModalInvocationResponse)
async def invoke_modal_fn(
    body: ModalInvocationRequest,
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    modal_client: modal.Client = Depends(get_modal_client),
    modal_vip: bool = Depends(modal_vip),
    under_modal_usage_limit: bool = Depends(under_modal_usage_limit),
    db: AsyncSession = Depends(get_db_session),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")
    # We want to mimic the behavior of the modal.Function._call_function method when the sdk hits this route.
    # In their code, this means creating an `_Invocation` object to both serialize arguments and build a request,
    # then awaiting a run_function helper to both collect and de-serialize the results.
    # (see: https://github.com/modal-labs/modal-client/blob/9507909d066785591b1d4f79f76b9e3ec4a07a33/modal/functions.py#L1191)

    # In this route we want to mimic their logic as closely as possible modulo (de-)serialization, with those steps performed on the user's machine
    # (like it would if they were using modal directly).
    #
    # fetch function from db
    modal_fn: ModalFunction | None = await ModalFunction.get(db, id=body.function_id)
    if modal_fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Modal Function with id {body.function_id} found.",
        )

    app_name = modal_fn.modal_app.app_name
    function_name = modal_fn.function_name
    log = logger.bind(app_name=app_name, function_name=function_name)

    # fetch the function from modal
    log.info("fetching function object from modal")
    function = await modal.functions._Function.lookup(
        app_name=modal_fn.modal_app.app_name,
        tag=modal_fn.function_name,
        environment_name=settings.MODAL_ENV,
        client=modal_client,
    )

    # create the _Invocation object
    log.info("Requesting invocation with modal")
    invocation_time = time.time()
    invocation = await _create_invocation(
        function, body.args_kwargs_serialized, modal_client
    )

    outputs_response = await invocation.pop_function_call_outputs(
        timeout=None, clear_on_success=True
    )
    execution_time_seconds = time.time() - invocation_time
    log.debug("received modal RPC response", outputs_response=outputs_response)

    usage = estimate_usage(function, execution_time_seconds)
    log = logger.bind(estimated_usage=usage)

    db.add(
        ModalInvocation(
            user_id=user.id,
            function_id=modal_fn.id,
            execution_time_seconds=execution_time_seconds,
            estimated_usage=usage,
        )
    )
    await db.commit()

    if not outputs_response.outputs:
        log.warning("No outputs received from function call")
        raise Exception("No outputs received from function call")

    output: api_pb2.FunctionGetOutputsItem = outputs_response.outputs[0]

    log.info("Invoked modal function")
    # we duplicate enough of the modal response schema that modal can process the
    # results "naturally" itself on the client side. (including e.g. formatting
    # the traceback for the user if things went wrong)
    return output


async def _create_invocation(
    function: modal.Function,
    args_kwargs_serialized: bytes,
    client: modal.Client,
    invocation_type=api_pb2.FUNCTION_CALL_INVOCATION_TYPE_SYNC_LEGACY,
) -> modal.functions._Invocation:
    function_id = function._invocation_function_id()
    # build the input payload with pre-serialized args
    inputs_item = api_pb2.FunctionPutInputsItem(
        input=api_pb2.FunctionInput(
            args=args_kwargs_serialized,
            data_format=api_pb2.DATA_FORMAT_PICKLE,
            method_name="",
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
        return modal.functions._Invocation(client.stub, function_call_id, client)

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
    return modal.functions._Invocation(client.stub, function_call_id, client)
