from fastapi import Request
from fastapi.responses import JSONResponse


class ModalException(Exception):
    def __init__(
        self,
        detail: str,
        status_code=400,
        suggested_fix: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.suggested_fix = suggested_fix


def handle_modal_exception(request: Request, error: ModalException):
    content = {
        "detail": error.detail,
        "suggested_fix": error.suggested_fix,
    }

    return JSONResponse(
        status_code=error.status_code,
        content=content,
    )
