import time
import uuid

import structlog
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


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
        except HTTPException:
            raise
        except Exception:
            logger = structlog.get_logger()
            logger.error(
                "Unhandled exception",
                exc_info=True,
                method=request.method,
                path=request.url.path,
            )

            return JSONResponse(
                status_code=500, content={"detail": "Internal Server Error"}
            )
