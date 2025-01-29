from datetime import datetime
from typing import Awaitable, Callable

from modal_proto import api_pb2
from sqlalchemy.ext.asyncio import AsyncSession

import modal
from modal._utils.grpc_utils import retry_transient_errors
from src.api.dependencies.database import get_db_session_maker
from src.config import Settings
from src.exceptions.modal import ModalException
from src.models.modal.invocations import ModalInvocation
from src.models.modal.modal_app import ModalApp
from src.models.modal.modal_function import ModalFunction

from .status import AsyncModalJobStatus
from .usage import estimate_usage


async def cancel_modal_invocation(invocation: ModalInvocation, client: modal.Client):
    request: api_pb2.FunctionCallCancelRequest = api_pb2.FunctionCallCancelRequest(
        function_call_id=invocation.function_call_id,
        terminate_containers=True,
    )
    await retry_transient_errors(client.stub.FunctionCallCancel, request)


async def resolve_modal_invocation(
    invocation: ModalInvocation,
    status: AsyncModalJobStatus,
    session: AsyncSession,
):
    if func := await ModalFunction.get(session, id=invocation.function_id):
        invocation.date_resolved = datetime.now()
        execution_time = (
            invocation.date_resolved - invocation.date_invoked
        ).total_seconds()
        invocation.estimated_usage = estimate_usage(func, execution_time)
        invocation.status = status
        await session.commit()
    else:
        raise ValueError(f"No Modal Function with id: {id} found!")


async def monitor_modal_invocation(
    invocation: modal.functions._Invocation,
    db_invocation: ModalInvocation,
    client: modal.Client,
    settings: Settings,
):
    session_maker = await get_db_session_maker(settings=settings)
    async with session_maker() as session:
        if inv := await ModalInvocation.get(session, id=db_invocation.id):
            try:
                # Try and get the invocation outputs
                outputs_response = await invocation.pop_function_call_outputs(
                    timeout=settings.MODAL_TIMEOUT_SECONDS,
                    clear_on_success=True,
                )
                # If we have outputs, the invocation suceeded, write the outputs to the DB
                if outputs_response.outputs:
                    inv.output = outputs_response.outputs[0].SerializeToString()
                    await resolve_modal_invocation(
                        inv, AsyncModalJobStatus.DONE, session
                    )
                    await session.commit()
                    return
                # If there are no outputs and unfinished inputs the invocation has timed out, cancel it!
                if outputs_response.num_unfinished_inputs > 0:
                    await cancel_modal_invocation(inv, client)
                    inv.error = "Timed out!"
                    await resolve_modal_invocation(
                        inv, AsyncModalJobStatus.TIMED_OUT, session
                    )
                    raise ModalException("Modal Invocation Timed out!", status_code=408)
                else:
                    raise ValueError(f"{outputs_response}")
            except ModalException:
                # Reraise the exception if we already wrapped it in a ModalException
                raise
            except Exception as e:
                # Otherwise, write the error to the DB
                inv.error = str(e)
                status = AsyncModalJobStatus.ERROR
                await resolve_modal_invocation(inv, status, session)
                await session.commit()


async def monitor_modal_deployment(
    deploy_func: Callable[..., Awaitable[None]],
    deploy_config: dict[str, str | bytes],
    app_id: int,
    settings: Settings,
):
    session_maker = await get_db_session_maker(settings=settings)

    try:
        await deploy_func(deploy_config)
        async with session_maker() as session:
            if modal_app := await ModalApp.get(session, id=app_id):
                modal_app.deploy_status = AsyncModalJobStatus.DONE
                await session.commit()
    except Exception as e:
        async with session_maker() as session:
            if modal_app := await ModalApp.get(session, id=app_id):
                modal_app.deploy_error = str(e)
                modal_app.deploy_status = AsyncModalJobStatus.ERROR
                await session.commit()
