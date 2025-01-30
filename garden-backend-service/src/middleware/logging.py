import time
import uuid
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from src.exceptions.modal import ModalException, handle_modal_exception
from src.exceptions.utils import format_traceback


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
