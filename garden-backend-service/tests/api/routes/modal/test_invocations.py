from unittest.mock import AsyncMock, MagicMock

import pytest
from modal_proto import api_pb2

from src.api.schemas.modal.invocations import (
    ModalInvocationRequest,
    ModalInvocationResponse,
)


@pytest.mark.asyncio
async def test_invoke_modal_fn(
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
):
    # Mock the modal Function and _Invocation
    mock_function = MagicMock()
    mock_function._invocation_function_id.return_value = "mock_function_id"
    mock_invocation = AsyncMock()
    mock_invocation.pop_function_call_outputs.return_value = MagicMock(
        outputs=[
            api_pb2.FunctionGetOutputsItem(
                result=api_pb2.GenericResult(status=0, data=b"mock_result_data"),
                data_format=api_pb2.DATA_FORMAT_PICKLE,
            )
        ]
    )

    mocker.patch("modal.functions._Function.lookup", return_value=mock_function)
    mocker.patch("modal.functions._Invocation", return_value=mock_invocation)

    # Mock retry_transient_errors to avoid outbound network calls
    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.side_effect = [
        MagicMock(
            function_call_id="mock_call_id", pipelined_inputs=["mock_input"]
        ),  # FunctionMap response
    ]

    # Prepare the request payload
    mock_request_body = ModalInvocationRequest(
        app_name="test_app",
        function_name="test_app",
        args_kwargs_serialized=b"mock_input_data",
    ).model_dump()

    # Send the request
    response = await client.post("/modal-invocations", json=mock_request_body)

    assert response.status_code == 200
    response_data = response.json()
    assert "result" in response_data
    assert response_data["result"]["status"] == 0

    assert response_data["data_format"] == api_pb2.DATA_FORMAT_PICKLE

    # check that schema converts to/from bytes as expected
    assert ModalInvocationResponse(**response_data).result.data == b"mock_result_data"
    assert (
        response_data["result"]["data"] == "bW9ja19yZXN1bHRfZGF0YQ=="
    )  # b64 encoded b"mock_result_data"

    # Verify that the mocks were called as expected
    mock_function._invocation_function_id.assert_called_once()
    mock_invocation.pop_function_call_outputs.assert_called_once_with(
        timeout=None, clear_on_success=True
    )
    assert mock_retry.call_count == 1
