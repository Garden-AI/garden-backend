from fastapi import Request
from fastapi.responses import JSONResponse


class ModalException(Exception):
    def __init__(
        self,
        detail: str,
        status_code=400,
        suggested_fix: str | None = None,
        deployment_output: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.suggested_fix = suggested_fix
        self.deployment_output = deployment_output


def handle_modal_exception(request: Request, error: ModalException):
    content = {
        "detail": error.detail,
        "suggested_fix": error.suggested_fix,
    }

    if error.deployment_output is not None:
        content["deployment_output"] = error.deployment_output

    return JSONResponse(
        status_code=error.status_code,
        content=content,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )
