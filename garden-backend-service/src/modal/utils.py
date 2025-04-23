from datetime import datetime
from typing import Awaitable, Callable, Mapping

from modal_proto import api_pb2
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

import modal
import modal._functions
from modal._utils.grpc_utils import retry_transient_errors
from src.api.dependencies.database import get_db_session_maker
from src.config import Settings
from src.exceptions.modal import ModalException
from src.models.modal.invocations import ModalInvocationResult
from src.models.modal.modal_app import ModalApp
from src.models.modal.modal_function import ModalFunction

from .status import AsyncModalJobStatus
from .usage import estimate_usage

log = get_logger(__name__)


async def cancel_modal_invocation(result: ModalInvocationResult, client: modal.Client):
    request: api_pb2.FunctionCallCancelRequest = api_pb2.FunctionCallCancelRequest(
        function_call_id=result.function_call_id,
        terminate_containers=True,
    )
    await retry_transient_errors(client.stub.FunctionCallCancel, request)


async def resolve_modal_invocation(
    result: ModalInvocationResult,
    status: AsyncModalJobStatus,
    session: AsyncSession,
):
    if func := await ModalFunction.get(session, id=result.function_id):
        result.log.date_resolved = datetime.now()
        execution_time = (
            result.log.date_resolved - result.log.date_invoked
        ).total_seconds()
        result.log.estimated_usage = estimate_usage(func, execution_time)
        result.status = status
        await session.commit()
    else:
        raise ValueError(f"No Modal Function with id: {id} found!")


async def monitor_modal_invocation(
    invocation: modal._functions._Invocation,
    db_result: ModalInvocationResult,
    client: modal.Client,
    settings: Settings,
):
    session_maker = await get_db_session_maker(settings=settings)
    async with session_maker() as session:
        if result := await ModalInvocationResult.get(session, id=db_result.id):
            try:
                # Try and get the invocation outputs
                outputs_response = await invocation.pop_function_call_outputs(
                    timeout=settings.MODAL_TIMEOUT_SECONDS,
                    clear_on_success=True,
                )
                # If we have outputs, the invocation suceeded, write the outputs to the DB
                if outputs_response.outputs:
                    result.output = outputs_response.outputs[0].SerializeToString()
                    await resolve_modal_invocation(
                        result, AsyncModalJobStatus.DONE, session
                    )
                    await session.commit()
                    return
                # If there are no outputs and unfinished inputs the invocation has timed out, cancel it!
                if outputs_response.num_unfinished_inputs > 0:
                    await cancel_modal_invocation(result, client)
                    result.error = "Timed out!"
                    await resolve_modal_invocation(
                        result, AsyncModalJobStatus.TIMED_OUT, session
                    )
                    raise ModalException("Modal Invocation Timed out!", status_code=408)
                else:
                    raise ValueError(f"{outputs_response}")
            except ModalException:
                # Reraise the exception if we already wrapped it in a ModalException
                raise
            except Exception as e:
                # Otherwise, write the error to the DB
                result.error = str(e)
                status = AsyncModalJobStatus.ERROR
                await resolve_modal_invocation(result, status, session)
                await session.commit()


async def monitor_modal_deployment(
    deploy_func: Callable[..., Awaitable[dict]],
    deploy_config: Mapping[str, str | bytes],
    app_id: int,
    settings: Settings,
):
    """Background task to monitor the deployment of a modal app.

    Args:
        deploy_func: The function to deploy the app
        deploy_config: The config for the deployment
        app_id: The id (our database id) of the app to deploy
        settings: application settings so we can get a db session outside of the request lifecycle
    """
    session_maker = await get_db_session_maker(settings=settings)

    deploy_status = AsyncModalJobStatus.PENDING
    deploy_error = None
    modal_app_id = None
    try:
        # attempt to deploy the app
        result = await deploy_func(deploy_config)
        modal_app_id = result["app_id"]
        deploy_status = AsyncModalJobStatus.DONE
        deploy_error = None
    except Exception as e:
        deploy_status = AsyncModalJobStatus.ERROR
        deploy_error = str(e)
    finally:
        # update the db record with the final status
        async with session_maker() as session:
            if modal_app := await ModalApp.get(session, id=app_id):
                log.info(
                    f"Updating modal app {app_id} with status {deploy_status} and error {deploy_error}"
                )
                modal_app.deploy_status = deploy_status
                modal_app.deploy_error = deploy_error
                modal_app.modal_app_id = str(modal_app_id)
                await session.commit()
