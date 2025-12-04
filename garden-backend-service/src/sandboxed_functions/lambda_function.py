import io
import sys
import traceback
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
    except Exception as e:
        print(f"Failed to import Modal app: {e}")
        print(traceback.format_exc())
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
        name: extract_from_spec(func.spec, specs) for name, func in functions.items()
    }


def extract_from_spec(
    spec: modal._functions._FunctionSpec, keys: list[str]
) -> dict[str, Any]:
    """Return a new dict with only the keys matching the given list.

    Raises `ModalException` when a given key is not present in `spec`
    """
    try:
        return {key: getattr(spec, key) for key in keys}
    except Exception as e:
        print(f"Failed to extract specs: {e}")
        print(traceback.format_exc())
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


def deploy_modal_app(args: DeployModalAppArgs):
    import os

    from modal import enable_output
    from modal.client import Client
    from modal.environments import ensure_env
    from modal.runner import deploy_app

    os.environ["MODAL_AUTOMOUNT"] = "False"

    env, file_contents, app_name, token_id, token_secret = (
        args["env"],
        args["file_contents"],
        args["app_name"],
        args["token_id"],
        args["token_secret"],
    )

    # Create a StringIO object to capture stdout
    output_capture = io.StringIO()
    original_stdout = sys.stdout

    try:
        # Redirect stdout to our StringIO object
        sys.stdout = output_capture

        with enable_output():
            ensure_env(env)
            app = get_app_from_file_contents(file_contents)
            client = Client.from_credentials(token_id, token_secret)
            try:
                res = deploy_app(
                    app, name=app_name, client=client, environment_name=env
                )
                captured_output = output_capture.getvalue()
                return {"app_id": res.app_id, "deployment_output": captured_output}
            except Exception as e:
                # Explicitly construct our response here to ensure suggested_fix is included
                captured_output = output_capture.getvalue()
                if "image build" in str(e).lower():
                    detail = f"Deployment failed during container build: {e}"
                    suggested_fix = "Try running the file locally with `modal run <filename>.py` to debug the issue."
                else:
                    detail = f"Deployment failed for unknown reason: {e}"
                    suggested_fix = "Check your Modal file for errors and try again."

                # Return a properly formatted error response
                return {
                    "ModalException": {
                        "detail": detail,
                        "suggested_fix": suggested_fix,
                        "status_code": 400,
                        "deployment_output": captured_output,
                    }
                }
    finally:
        # Restore original stdout
        sys.stdout = original_stdout


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
