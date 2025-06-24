import json
import time
import uuid
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from src.exceptions.modal import ModalException, handle_modal_exception
from src.exceptions.utils import format_traceback


class MCPBypassMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = structlog.get_logger()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            self.logger.info(
                "MCP request bypass", method=scope["method"], path=scope["path"]
            )

            try:
                current_app = self.app
                while hasattr(current_app, "app"):
                    if "FastAPI" in str(type(current_app)):
                        break
                    current_app = current_app.app

                await current_app(scope, receive, send)
                self.logger.info(
                    "MCP request completed successfully", path=scope["path"]
                )
                return
            except HTTPException as http_exception:
                self.logger.info(
                    "HTTP exception in MCP request",
                    path=scope["path"],
                    status_code=http_exception.status_code,
                )

                # Send the proper HTTP response
                await send(
                    {
                        "type": "http.response.start",
                        "status": http_exception.status_code,
                        "headers": [[b"content-type", b"application/json"]],
                    }
                )

                response_body = json.dumps(
                    {
                        "detail": http_exception.detail,
                        "status_code": http_exception.status_code,
                    }
                ).encode()

                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                    }
                )
                return
            except Exception as e:
                self.logger.error(
                    "Unhandled exception in MCP request",
                    method=scope["method"],
                    path=scope["path"],
                    error=str(e),
                    exc_info=True,
                )

                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [[b"content-type", b"application/json"]],
                    }
                )

                response_body = json.dumps(
                    {"detail": "Internal server error", "status_code": 500}
                ).encode()

                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                    }
                )
                return

        await self.app(scope, receive, send)


def add_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Add request ID to the structlog context when processing the request
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)

        # Add request ID to the response headers
        response.headers["X-Request-ID"] = request_id

        return response


def add_process_time_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def process_time_middleware(
        request: Request, call_next: Callable
    ) -> Response:
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        formatted_process_time = f"{process_time:.2f}"

        # Log the request details and timing
        logger = structlog.get_logger()
        logger.info(
            "Request processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=formatted_process_time,
        )

        response.headers["X-Process-Time"] = formatted_process_time

        return response


def add_error_handling_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def error_handling_middleware(
        request: Request, call_next: Callable
    ) -> Response:
        try:
            return await call_next(request)
        except ModalException as e:
            logger = structlog.get_logger()
            filtered_stacktrace = format_traceback(e)
            logger.error(
                "Modal Exception",
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
                stack_trace=filtered_stacktrace,
                detail=e.detail,
                suggested_fix=e.suggested_fix,
            )
            return handle_modal_exception(request, e)
        except Exception as e:
            filtered_stacktrace = format_traceback(e)
            logger = structlog.get_logger()
            logger.error(
                f"Unhandled exception: {str(e)}",
                stack_trace=filtered_stacktrace,
                method=request.method,
                path=request.url.path,
            )

            return JSONResponse(
                status_code=500, content={"detail": f"Internal Server Error: {str(e)}"}
            )
