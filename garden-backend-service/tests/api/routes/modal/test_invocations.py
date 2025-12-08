from unittest.mock import AsyncMock, MagicMock

import pytest
from modal_proto import api_pb2

from src.api.schemas.modal.invocations import (
    ModalBlobUploadURLRequest,
    ModalInvocationRequest,
)
from src.modal.status import AsyncModalJobStatus


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
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
    mock_function.object_id = "mock_function_id"
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

    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=mock_invocation,
    )
    mocker.patch(
        "src.modal.utils.estimate_usage",
        return_value=1.0,
    )
    # Prepare the request payload
    mock_request_body = ModalInvocationRequest(
        function_id=test_function_id,  # from above
        args_kwargs_serialized=b"mock_input_data",
    ).model_dump()

    # Send the request to the async endpoint
    response = await client.post("/modal-invocations/async", json=mock_request_body)
    assert response.status_code == 200
    response_data = response.json()

    # Assert response structure and status
    assert "id" in response_data
    assert response_data["status"] == "pending"
    invocation_id = response_data["id"]

    # Mock the database objects for the GET request
    mock_db_log = MagicMock()
    mock_db_log.id = invocation_id
    mock_db_log.user_id = 1
    mock_db_log.function_id = test_function_id
    mock_db_log.date_invoked = "2024-01-01T00:00:00"
    mock_db_log.date_resolved = None
    mock_db_log.estimated_usage = 1.0

    mock_db_result = MagicMock()
    mock_db_result.id = invocation_id
    mock_db_result.status = AsyncModalJobStatus.DONE
    mock_db_result.output = api_pb2.FunctionGetOutputsItem(
        result=api_pb2.GenericResult(status=0, data=b"mock_result_data"),
        data_format=api_pb2.DATA_FORMAT_PICKLE,
    ).SerializeToString()
    mock_db_result.error = None
    mock_db_result.log = mock_db_log
    mock_db_log.result = mock_db_result

    # Mock database queries for GET request
    mocker.patch(
        "src.api.routes.modal.invocations.ModalInvocationResult.get",
        return_value=mock_db_result,
    )

    # Get the invocation result
    response = await client.get(f"/modal-invocations/{invocation_id}")
    assert response.status_code == 200
    response_data = response.json()

    # Assert the result structure
    assert response_data["id"] == invocation_id
    assert response_data["status"] == "done"
    assert "result" in response_data
    assert response_data["result"]["status"] == 0
    assert (
        response_data["result"]["data"] == "bW9ja19yZXN1bHRfZGF0YQ=="
    )  # b64 encoded b"mock_result_data"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn_rejects_request_if_user_is_over_usage_limit(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
    override_usage_limit_dependency,
):
    # first, "deploy" a modal function to invoke
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    test_function_id = response_data["modal_function_ids"][0]

    mock_function = MagicMock()
    mock_function.object_id = "mock_function_id"
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "mock_call_id"

    # Mock the new _fetch_modal_function helper
    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=mock_invocation,
    )

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

    # Send the request to the async endpoint
    response = await client.post("/modal-invocations/async", json=mock_request_body)
    assert response.status_code == 403
    assert "User is over Modal usage limit" in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn_async(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # Deploy a modal function to invoke
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    test_function_id = response_data["modal_function_ids"][0]

    mock_function = MagicMock()
    mock_function.object_id = "mock_function_id"
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

    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=mock_invocation,
    )

    # Prepare request payload
    mock_request_body = ModalInvocationRequest(
        function_id=test_function_id,
        args_kwargs_serialized=b"mock_input_data",
    ).model_dump()

    # Send the async POST request
    response = await client.post("/modal-invocations/async", json=mock_request_body)
    assert response.status_code == 200
    response_data = response.json()

    # Assert response structure and status
    assert "id" in response_data
    assert response_data["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_invocation_output(
    client,
    override_get_modal_client_dependency,
    mock_db_session,
    override_get_settings_dependency,
    mocker,
):
    # Create mock database objects
    mock_db_log = MagicMock()
    mock_db_log.id = 1
    mock_db_log.user_id = 1
    mock_db_log.function_id = 1
    mock_db_log.date_invoked = "2024-01-01T00:00:00"
    mock_db_log.date_resolved = None
    mock_db_log.estimated_usage = 1.0

    mock_db_result = MagicMock()
    mock_db_result.id = 1
    mock_db_result.status = AsyncModalJobStatus.DONE
    mock_db_result.output = api_pb2.FunctionGetOutputsItem(
        result=api_pb2.GenericResult(status=0, data=b"mock_result_data"),
        data_format=api_pb2.DATA_FORMAT_PICKLE,
    ).SerializeToString()
    mock_db_result.error = None
    mock_db_result.log = mock_db_log
    mock_db_log.result = mock_db_result

    # Patch ModalInvocationResult.get to return the mock object
    mocker.patch(
        "src.api.routes.modal.invocations.ModalInvocationResult.get",
        return_value=mock_db_result,
    )

    # Send the GET request
    response = await client.get("/modal-invocations/1")
    assert response.status_code == 200
    response_data = response.json()

    # Assert response structure
    assert response_data["id"] == 1
    assert response_data["status"] == "done"
    assert "result" in response_data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_blob_upload_url_single_part(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
):
    # Mock Modal's BlobCreate RPC response
    mock_blob_response = MagicMock()
    mock_blob_response.blob_id = "test-blob-id"
    mock_blob_response.upload_url = "https://test-upload-url"
    mock_blob_response.WhichOneof.return_value = None  # Single-part upload

    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.return_value = mock_blob_response

    request_body = ModalBlobUploadURLRequest(
        content_md5="test-md5",
        content_sha256_base64="test-sha256",
        content_length=1000,
    ).model_dump()

    response = await client.post("/modal-invocations/blob-uploads", json=request_body)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["blob_id"] == "test-blob-id"
    assert response_data["upload_type"] == "single"
    assert response_data["upload_url"] == "https://test-upload-url"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_blob_upload_url_multipart(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
):
    # Mock Modal's BlobCreate RPC response for multipart upload
    mock_blob_response = MagicMock()
    mock_blob_response.blob_id = "test-blob-id"
    mock_blob_response.multipart.part_length = 5_000_000
    mock_blob_response.multipart.upload_urls = [
        "https://test-upload-url-part1",
        "https://test-upload-url-part2",
    ]
    mock_blob_response.multipart.completion_url = "https://test-completion-url"
    mock_blob_response.WhichOneof.return_value = "multipart"

    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.return_value = mock_blob_response

    request_body = ModalBlobUploadURLRequest(
        content_md5="test-md5",
        content_sha256_base64="test-sha256",
        content_length=10_000_000,
    ).model_dump()

    response = await client.post("/modal-invocations/blob-uploads", json=request_body)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["blob_id"] == "test-blob-id"
    assert response_data["upload_type"] == "multipart"
    assert response_data["multipart"]["part_length"] == 5_000_000
    assert len(response_data["multipart"]["upload_urls"]) == 2
    assert response_data["multipart"]["completion_url"] == "https://test-completion-url"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_modal_fn_with_blob_args(
    client,
    mock_db_session,
    mock_modal_publisher_auth_state,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
    mock_modal_app_create_request_one_function,
    override_sandboxed_functions,
):
    # First deploy a modal function to invoke
    response = await client.post(
        "/modal-apps", json=mock_modal_app_create_request_one_function
    )
    assert response.status_code == 200
    response_data = response.json()
    test_function_id = response_data["modal_function_ids"][0]

    # Mock the modal Function and _Invocation
    mock_function = MagicMock()
    mock_function.object_id = "mock_function_id"
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

    # Mock the new _fetch_modal_function helper
    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )
    mocker.patch(
        "src.api.routes.modal.invocations._create_invocation",
        return_value=mock_invocation,
    )
    mocker.patch("src.modal.utils.estimate_usage", return_value=1.0)

    # Mock retry_transient_errors
    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.side_effect = [
        MagicMock(function_call_id="mock_call_id", pipelined_inputs=["mock_input"]),
    ]

    # Prepare request payload using blob_id instead of serialized args
    mock_request_body = ModalInvocationRequest(
        function_id=test_function_id,
        args_blob_id="test-blob-id",
    ).model_dump()

    # Send the request to the async endpoint
    response = await client.post("/modal-invocations/async", json=mock_request_body)
    assert response.status_code == 200
    response_data = response.json()

    # Assert response structure and status
    assert "id" in response_data
    assert response_data["status"] == "pending"
    invocation_id = response_data["id"]

    # Mock the database objects for the GET request
    mock_db_log = MagicMock()
    mock_db_log.id = invocation_id
    mock_db_log.user_id = 1
    mock_db_log.function_id = test_function_id
    mock_db_log.date_invoked = "2024-01-01T00:00:00"
    mock_db_log.date_resolved = None
    mock_db_log.estimated_usage = 1.0

    mock_db_result = MagicMock()
    mock_db_result.id = invocation_id
    mock_db_result.status = AsyncModalJobStatus.DONE
    mock_db_result.output = api_pb2.FunctionGetOutputsItem(
        result=api_pb2.GenericResult(status=0, data=b"mock_result_data"),
        data_format=api_pb2.DATA_FORMAT_PICKLE,
    ).SerializeToString()
    mock_db_result.error = None
    mock_db_result.log = mock_db_log
    mock_db_log.result = mock_db_result

    # Mock database query for GET request
    mocker.patch(
        "src.api.routes.modal.invocations.ModalInvocationResult.get",
        return_value=mock_db_result,
    )

    # Get the invocation result
    response = await client.get(f"/modal-invocations/{invocation_id}")
    assert response.status_code == 200
    response_data = response.json()

    # Assert the result structure
    assert response_data["id"] == invocation_id
    assert response_data["status"] == "done"
    assert "result" in response_data
    assert response_data["result"]["status"] == 0
    assert (
        response_data["result"]["data"] == "bW9ja19yZXN1bHRfZGF0YQ=="
    )  # b64 encoded b"mock_result_data"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_invocation_output_with_blob_result(
    client,
    mock_db_session,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
):
    # Create mock database objects with blob-based result
    mock_db_log = MagicMock()
    mock_db_log.id = 1
    mock_db_log.user_id = 1
    mock_db_log.function_id = 1
    mock_db_log.date_invoked = "2024-01-01T00:00:00"
    mock_db_log.date_resolved = None
    mock_db_log.estimated_usage = 1.0

    mock_db_result = MagicMock()
    mock_db_result.id = 1
    mock_db_result.status = AsyncModalJobStatus.DONE

    # Create output with blob reference instead of inline data
    test_result = api_pb2.GenericResult(status=0, data_blob_id="test-result-blob-id")
    output_item = api_pb2.FunctionGetOutputsItem(
        result=test_result,
        data_format=api_pb2.DATA_FORMAT_PICKLE,
    )
    mock_db_result.output = output_item.SerializeToString()
    mock_db_result.error = None
    mock_db_result.log = mock_db_log
    mock_db_log.result = mock_db_result

    # Mock blob URL retrieval
    mock_blob_response = MagicMock()
    mock_blob_response.download_url = "https://test-download-url"

    mock_retry = mocker.patch("src.api.routes.modal.invocations.retry_transient_errors")
    mock_retry.return_value = mock_blob_response

    # Mock database query
    mocker.patch(
        "src.api.routes.modal.invocations.ModalInvocationResult.get",
        return_value=mock_db_result,
    )
    response = await client.get("/modal-invocations/1")
    assert response.status_code == 200
    response_data = response.json()

    # Verify response structure with blob URL
    assert response_data["id"] == 1
    assert response_data["status"] == "done"
    assert "result" in response_data
    assert response_data["result"]["data_blob_url"] == "https://test-download-url"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_modal_invocation_restarts_dropped_background_task(
    client,
    mock_db_session,
    override_get_settings_dependency,
    override_get_modal_client_dependency,
    mocker,
):
    """Test that a dropped background task is restarted when fetching pending invocation."""
    # Create mock modal function for rebuilding invocation
    mock_modal_fn = MagicMock()
    mock_modal_fn.id = 1
    mock_modal_fn.function_name = "test_function"
    mock_modal_fn.modal_app = MagicMock()
    mock_modal_fn.modal_app.app_name = "test_app"

    # Create mock database objects for a pending invocation
    mock_db_log = MagicMock()
    mock_db_log.id = 1
    mock_db_log.user_id = 1
    mock_db_log.function_id = 1
    mock_db_log.date_invoked = "2024-01-01T00:00:00"
    mock_db_log.date_resolved = None

    mock_db_result = MagicMock()
    mock_db_result.id = 1
    mock_db_result.function_id = 1
    mock_db_result.function_call_id = "test_function_call_id"
    mock_db_result.status = AsyncModalJobStatus.PENDING  # Still pending
    mock_db_result.output = None
    mock_db_result.error = None
    mock_db_result.log = mock_db_log
    mock_db_log.result = mock_db_result

    # Mock the database queries
    mocker.patch(
        "src.api.routes.modal.invocations.ModalInvocationResult.get",
        return_value=mock_db_result,
    )
    mocker.patch(
        "src.api.routes.modal.invocations.ModalFunction.get",
        return_value=mock_modal_fn,
    )

    # Mock _fetch_modal_function and _create_invocation for rebuilding
    mock_function = MagicMock()
    mock_function.object_id = "mock_function_id"
    mock_invocation = AsyncMock()
    mock_invocation.function_call_id = "test_function_call_id"

    mocker.patch(
        "src.api.routes.modal.invocations._fetch_modal_function",
        return_value=mock_function,
    )

    # Mock the invocation reconstruction - it should return an invocation with the same function_call_id
    mock_create_invocation = mocker.patch(
        "src.api.routes.modal.invocations._create_invocation_from_function_call_id",
        return_value=mock_invocation,
    )

    # Mock the background task monitoring
    mock_monitor = mocker.patch(
        "src.api.routes.modal.invocations.monitor_modal_invocation"
    )

    # Send the GET request for a pending invocation with no active background task
    response = await client.get("/modal-invocations/1")
    assert response.status_code == 200
    response_data = response.json()

    # Should return pending status
    assert response_data["id"] == 1
    assert response_data["status"] == "pending"

    # Should have recreated the invocation from the function_call_id
    mock_create_invocation.assert_called_once()

    # Should have started a new background monitoring task
    mock_monitor.assert_called_once()
