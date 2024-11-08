import dataclasses
from typing import Any, TypedDict

import modal


# Copied for now
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


class ValidateModalFileArgs(TypedDict):
    file_contents: str


class DeployModalAppArgs(TypedDict):
    file_contents: str
    app_name: str
    token_id: str
    token_secret: str
    env: str


def write_to_tmp_file(file_contents: str):
    import tempfile

    tmp_file_path = tempfile.mktemp() + ".py"
    with open(tmp_file_path, "w") as f:
        f.write(file_contents)
    return tmp_file_path


def get_app_from_file_contents(file_contents: str):
    from modal.cli.import_refs import import_app

    tmp_file_path = write_to_tmp_file(file_contents)

    try:
        user_app = import_app(tmp_file_path)
    except Exception:
        raise ModalException(
            detail="Failed to import app from Modal File",
            suggested_fix="Make sure provided Modal file has a `modal.App` object called `app` in the global scope. e.g `app = modal.App('my-app')`",
        )
    return user_app


def get_function_specs(
    functions: dict[str, modal.Function],
    specs: list[str],
) -> dict[str, dict[str, Any]]:
    """Return function names mapped to their respective specs.

    Raises `ModalException` when a requested spec is not found,
    This behavior alerts us if/when Modal changes their `_FunctionSpec` schema
    """
    return {
        name: extract_from_dict(dataclasses.asdict(func.spec), specs)
        for name, func in functions.items()
    }


def extract_from_dict(d: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Return a new dict with only the keys matching the given list.

    Raises `ModalException` when a given key is not present in `d`
    """
    try:
        return {key: d[key] for key in keys}
    except Exception:
        raise ModalException(
            detail="Failed to parse function hardware spec.",
            status_code=500,
            suggested_fix="Please contact the Garden-AI dev team.",
        )


def validate_modal_file(args: ValidateModalFileArgs):
    user_app = get_app_from_file_contents(args["file_contents"])
    app_name = user_app.name
    functions = get_function_specs(
        user_app.registered_functions,
        ["gpus", "cpu", "memory"],
    )
    return {"app_name": app_name, "functions": functions}

    # TODO: confirm nothing dastardly on the app/functions


def deploy_modal_app(args: DeployModalAppArgs):
    import os

    from modal import enable_output
    from modal.cli.run import deploy_app, ensure_env
    from modal.client import Client

    os.environ["MODAL_AUTOMOUNT"] = "False"

    env, file_contents, app_name, token_id, token_secret = (
        args["env"],
        args["file_contents"],
        args["app_name"],
        args["token_id"],
        args["token_secret"],
    )

    with enable_output():
        ensure_env(env)
        app = get_app_from_file_contents(file_contents)
        client = Client.from_credentials(token_id, token_secret)
        res = deploy_app(app, name=app_name, client=client, environment_name=env)

    return {"app_id": res.app_id}


def lambda_handler(event, context):
    fn_name = event["fn_name"]
    fn_args = event["fn_args"]
    try:
        if fn_name == "deploy_modal_app":
            return deploy_modal_app(fn_args)
        elif fn_name == "validate_modal_file":
            return validate_modal_file(fn_args)
    except ModalException as e:
        return {
            "ModalException": {
                "detail": e.detail,
                "suggested_fix": e.suggested_fix,
                "status_code": e.status_code,
            }
        }
    except Exception as e:
        return {"Exception": {"detail": str(e)}}
