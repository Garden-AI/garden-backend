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
        if scope['type'] != "http":
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
            if message['type'] == "http.response.start":
                process_time = (time.time() - start_time) * 1000
                formatted_process_time = f"{process_time:.2f}"

                logger = structlog.get_logger()
                logger.info(
                    "Request processed",
                    method=scope["method"],
                    path=scope["path"],
                    status_code=message["status"],
                    process_time_ms=formatted_process_time
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
                suggest_fix=e.suggested_fix
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
                path=scope["path"]
            )

            await self._send_response(
                send,
                500,
                json.dumps({"detail": f"Internal Server Error: {str(e)}"}).encode()
            )
    
    async def _send_response(self, send: Send, status_code: int, body: bytes):
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [[b"content-type", b"application/json"]]
        })

        await send({
            "type": "http.response.body",
            "body": body
        })