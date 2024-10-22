from unittest.mock import AsyncMock, MagicMock

import pytest
from modal_proto import api_pb2

from src.api.schemas.modal.invocations import (
    ModalInvocationRequest,
    ModalInvocationResponse,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn(
    override_modal_vip,
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # first, "deploy" a modal function to invoke
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    test_function_id = response_data["modal_function_ids"][0]

    # Mock the modal Function and _Invocation
    mock_function = MagicMock()
    mock_function._invocation_function_id.return_value = "mock_function_id"
    mock_function.spec.return_value = {"cpu": 0.125, "gpus": "A100", "memory": None}
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "mock_call_id"
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
    mocker.patch(
        "src.api.routes.modal.invocations.estimate_usage",
        return_value=1.0,
    )

    # Mock retry_transient_errors to avoid outbound network calls
    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.side_effect = [
        MagicMock(
            function_call_id="mock_call_id", pipelined_inputs=["mock_input"]
        ),  # FunctionMap response
    ]

    # Prepare the request payload
    mock_request_body = ModalInvocationRequest(
        function_id=test_function_id,  # from above
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn_rejects_request_if_user_is_over_usage_limit(
    override_modal_vip,
    client,
    mock_db_session,
    override_authenticated_dependency,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # first, "deploy" a modal function to invoke
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    test_function_id = response_data["modal_function_ids"][0]

    mock_function = MagicMock()
    mock_function._invocation_function_id.return_value = "mock_function_id"
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "mock_call_id"
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
        MagicMock(
            function_call_id="mock_call_id", pipelined_inputs=["mock_input"]
        ),  # FunctionMap response
    ]

    # Prepare the request payload
    mock_request_body = ModalInvocationRequest(
        function_id=test_function_id,  # from above
        args_kwargs_serialized=b"mock_input_data",
    ).model_dump()

    # Simulate a lot of usage
    mocker.patch(
        "src.api.routes.modal.invocations.estimate_usage",
        return_value=10.0,
    )

    # Send the request
    response = await client.post("/modal-invocations", json=mock_request_body)
    assert response.status_code == 200

    # The next inovcation should fail because the user is over the usage limit
    response = await client.post("/modal-invocations", json=mock_request_body)
    assert response.status_code == 403
    assert "User is over Modal usage limit" in response.text
