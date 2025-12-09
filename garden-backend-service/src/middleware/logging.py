import json
import time
import uuid

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from src.exceptions.modal import ModalException, handle_modal_exception
from src.exceptions.utils import format_traceback


class AddRequestIDMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())

        if "state" not in scope.keys():
            scope["state"] = {}

        scope["state"]["X-Request-ID"] = request_id

        async def send_response_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append([b"X-Request-ID", request_id.encode()])
                message = {**message, "headers": headers}

            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            await self.app(scope, receive, send_response_wrapper)


class ProcessTimeMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_response_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = (time.time() - start_time) * 1000
                formatted_process_time = f"{process_time:.2f}"

                logger = structlog.get_logger()
                logger.info(
                    "Request processed",
                    method=scope["method"],
                    path=scope["path"],
                    status_code=message["status"],
                    process_time_ms=formatted_process_time,
                )
            await send(message)

        await self.app(scope, receive, send_response_wrapper)


class ErrorHandlingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        try:
            return await self.app(scope, receive, send)
        except ModalException as e:
            logger = structlog.get_logger()
            filtered_stacktrace = format_traceback(e)

            logger.error(
                "Modal Exception",
                method=scope["method"],
                path=scope["path"],
                status_code=e.status_code,
                stack_trace=filtered_stacktrace,
                detail=e.detail,
                suggest_fix=e.suggested_fix,
            )
            response = handle_modal_exception(None, e)
            await self._send_response(send, e.status_code, response.body)
        except Exception as e:
            logger = structlog.get_logger()
            filtered_stacktrace = format_traceback(e)

            logger.error(
                f"Unhandled exception: {str(e)}",
                stack_trace=filtered_stacktrace,
                method=scope["method"],
                path=scope["path"],
            )

            # Attempt to reset the ModalClient singleton if it's potentially responsible
            # This is safe to call even if the error wasn't Modal-related.
            try:
                from src.api.dependencies.modal import ModalClient

                await ModalClient.get_instance().reset()
            except Exception:
                pass  # Don't let clean-up failure mask the original error

            await self._send_response(
                send,
                500,
                json.dumps({"detail": f"Internal Server Error: {str(e)}"}).encode(),
            )

    async def _send_response(self, send: Send, status_code: int, body: bytes):
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [[b"content-type", b"application/json"]],
            }
        )

        await send({"type": "http.response.body", "body": body})


class HeaderLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))

        decoded_headers = {k.decode(): v.decode() for k, v in headers.items()}

        # Headers of interest for ALB/MCP debugging
        interesting_headers = {
            k: v
            for k, v in decoded_headers.items()
            if any(
                prefix in k.lower()
                for prefix in [
                    "x-forwarded",
                    "x-amzn",
                    "x-real-ip",
                    "authorization",
                    "origin",
                    "connection",
                    "upgrade",
                    "accept",
                    "cache-control",
                    "user-agent",
                    "host",
                ]
            )
        }

        logger = structlog.get_logger()
        logger.info(
            "Request headers",
            method=scope["method"],
            path=scope["path"],
            client_host=scope.get("client") or "unknown",
            headers=interesting_headers,
            total_header_count=len(decoded_headers),
        )

        await self.app(scope, receive, send)


class MCPKeepAliveMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            # Add keepalive headers for MCP endpoints
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))

                    headers.extend(
                        [
                            [b"connection", b"keep-alive"],
                            [b"keep-alive", b"timeout=300, max=1000"],
                            [b"x-accel-buffering", b"no"],  # Disable nginx buffering
                        ]
                    )
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)
