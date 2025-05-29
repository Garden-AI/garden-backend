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


async def _process_invocation_completion(
    invocation: modal._functions._Invocation,
    result: ModalInvocationResult,
    client: modal.Client,
    session: AsyncSession,
    settings: Settings,
):
    """Process the completion of a modal invocation and handle outputs, timeouts, and errors."""
    # Try and get the invocation outputs
    outputs_response = await invocation.pop_function_call_outputs(
        timeout=settings.MODAL_TIMEOUT_SECONDS,
        clear_on_success=True,
    )
    # If we have outputs, the invocation suceeded, write the outputs to the DB
    if outputs_response.outputs:
        result.output = outputs_response.outputs[0].SerializeToString()
        await resolve_modal_invocation(result, AsyncModalJobStatus.DONE, session)
        await session.commit()
        return
    # If there are no outputs and unfinished inputs the invocation has timed out, cancel it!
    if outputs_response.num_unfinished_inputs > 0:
        await cancel_modal_invocation(result, client)
        result.error = "Timed out!"
        await resolve_modal_invocation(result, AsyncModalJobStatus.TIMED_OUT, session)
        raise ModalException("Modal Invocation Timed out!", status_code=408)
    else:
        raise ValueError(f"{outputs_response}")


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
                await _process_invocation_completion(
                    invocation, result, client, session, settings
                )
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
    suggested_fix = None
    deployment_output = None

    try:
        # Attempt to deploy the app
        result = await deploy_func(deploy_config)

        # Handle success case
        if "app_id" in result:
            modal_app_id = result["app_id"]
            deployment_output = result.get("deployment_output")
            deploy_status = AsyncModalJobStatus.DONE
        # Handle error case when result contains ModalException
        elif "ModalException" in result:
            exception_data = result["ModalException"]
            deploy_status = AsyncModalJobStatus.ERROR
            deploy_error = exception_data.get("detail", "Unknown error")
            suggested_fix = exception_data.get("suggested_fix")
            deployment_output = exception_data.get("deployment_output")
        else:
            # Unexpected result format
            deploy_status = AsyncModalJobStatus.ERROR
            deploy_error = f"Unexpected result format: {result}"
    except ModalException as e:
        deploy_status = AsyncModalJobStatus.ERROR
        deploy_error = e.detail
        suggested_fix = e.suggested_fix
        # Extract deployment output if available
        if hasattr(e, "deployment_output"):
            deployment_output = e.deployment_output
    except Exception as e:
        deploy_status = AsyncModalJobStatus.ERROR
        deploy_error = str(e)

        # Check if the exception is actually a dict with ModalException info
        if isinstance(e, dict) and "ModalException" in e:
            exception_data = e["ModalException"]
            suggested_fix = exception_data.get("suggested_fix")
            deployment_output = exception_data.get("deployment_output")
        else:
            # Add suggested_fix based on error message
            error_str = str(e).lower()
            if "image build" in error_str or "failed with the exception" in error_str:
                suggested_fix = "Try running the file locally with `modal run <filename>.py` to debug the issue."
            elif "timeout" in error_str:
                suggested_fix = (
                    "The deployment is taking a long time. Wait a minute and try again."
                )
            else:
                suggested_fix = "Check your Modal file for errors and try again."
    finally:
        # update the db record with the final status
        async with session_maker() as session:
            if modal_app := await ModalApp.get(session, id=app_id):
                log.info(f"Updating modal app {app_id} with status {deploy_status}")
                modal_app.deploy_status = deploy_status
                modal_app.deploy_error = deploy_error
                modal_app.modal_app_id = str(modal_app_id) if modal_app_id else None
                modal_app.suggested_fix = suggested_fix
                modal_app.deployment_output = deployment_output
                await session.commit()
            else:
                log.error(
                    f"Could not find ModalApp with id {app_id} to update deployment status"
                )


async def lookup_app_id(
    app_name: str, modal_client: modal.client._Client, settings: Settings
) -> str | None:
    """Look up an app ID from Modal using AppListRequest.

    This is more reliable than AppGetByDeploymentNameRequest as it searches
    through all apps in the environment.

    Args:
        app_name: Name of the app in Modal
        modal_client: The Modal client instance
        settings: Application settings

    Returns:
        The app ID if found, None otherwise
    """
    request = api_pb2.AppListRequest(
        environment_name=settings.MODAL_ENV,
    )
    response = await retry_transient_errors(modal_client.stub.AppList, request)

    for app in response.apps:
        if app.name == app_name:
            return app.app_id
    return None


async def stop_modal_app(
    app_name: str,
    modal_client: modal.client._Client,
    settings: Settings,
    app_id: str | None = None,
):
    """Stop a running Modal app.

    Args:
        app_name: Name of the app in Modal
        modal_client: The Modal client instance
        settings: Application settings
        app_id: Optional app ID (will be looked up if not provided)
    """
    if app_id is None:
        app_id = await lookup_app_id(app_name, modal_client, settings)
        if app_id is None:
            log.warning(f"Could not find app ID for {app_name}, skipping stop request")
            return

    # Stop the app
    stop_request = api_pb2.AppStopRequest(
        app_id=app_id,
        source=api_pb2.APP_STOP_SOURCE_PYTHON_CLIENT,
    )
    await retry_transient_errors(modal_client.stub.AppStop, stop_request)
