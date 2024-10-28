import re
import time
import traceback
import uuid

import structlog
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.dependencies.modal import ModalException, handle_modal_exception


def filter_stacktrace(exc: Exception):
    """Filter the stack trace to include only the relevant part from the endpoint call to the error."""
    tb = traceback.extract_tb(exc.__traceback__)  # Extract the stack frames

    # Find the frame for the most recent dispatch call
    relevant_frames = []

    for frame in reversed(tb):  # Walk the stack from the bottom (most recent call)
        filename, lineno, funcname, text = frame

        # stop when we hit the inital call to the endpoint
        if funcname == "run_endpoint_function":
            break

        relevant_frames.append(frame)

    # If we found relevant frames, format them
    if relevant_frames:
        filtered_tb = traceback.format_list(
            reversed(relevant_frames)
        )  # Reverse to maintain original order
        cleaned_tb = [re.sub(r"(\^+)", "", line).strip() for line in filtered_tb]
        return "".join(cleaned_tb)

    # Fallback to the full traceback if no endpoint call was found
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


class LogRequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Add request ID to the structlog context when processing the request
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)

        # Add request ID to the response headers
        response.headers["X-Request-ID"] = request_id

        return response


class LogProcessTimeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response: Response = await call_next(request)

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


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except ModalException as e:
            logger = structlog.get_logger()
            filtered_stacktrace = filter_stacktrace(e)
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
        except HTTPException:
            raise
        except Exception as e:
            filtered_stacktrace = filter_stacktrace(e)
            logger = structlog.get_logger()
            logger.error(
                "Unhandled exception",
                stack_trace=filtered_stacktrace,
                method=request.method,
                path=request.url.path,
            )

            return JSONResponse(
                status_code=500, content={"detail": "Internal Server Error"}
            )
