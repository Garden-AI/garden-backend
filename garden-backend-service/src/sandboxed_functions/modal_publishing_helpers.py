import dataclasses
from typing import Any

import modal

app = modal.App("garden-publishing-helpers")

modal_helper_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "modal==0.64.126"
)

#
# Helper functions
#


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
        # TODO: identify failure modes and propagate those back
        raise e

    return user_app


#
# Functions that we want to run remotely to safely execute user-provided code
#


def validate_modal_file(file_contents: str):
    user_app = get_app_from_file_contents(file_contents)
    app_name = user_app.name
    functions = get_function_specs(
        user_app.registered_functions,
        ["gpus", "cpu", "memory"],
    )
    return {"app_name": app_name, "functions": functions}

    # TODO: confirm nothing dastardly on the app/functions


def get_function_specs(
    functions: dict[str, modal.Function],
    specs: list[str],
) -> dict[str, dict[str, Any]]:
    """Return function names mapped to their respective specs.

    Raises `KeyError` when a requested spec is not found,
    This behavior alerts us if/when Modal changes their `_FunctionSpec` schema
    """
    return {
        name: extract_from_dict(dataclasses.asdict(func.spec), specs)
        for name, func in functions.items()
    }


def extract_from_dict(d: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Return a new dict with only the keys matching the given list.

    Raises `KeyError` when a given key is not present in `d`
    """
    return {key: d[key] for key in keys}


@app.function(image=modal_helper_image)
def remote_validate_modal_file(file_contents: str):
    return validate_modal_file(file_contents)


def deploy_modal_app(
    file_contents: str, app_name: str, token_id: str, token_secret: str, env: str
):
    from modal import enable_output
    from modal.cli.run import deploy_app, ensure_env
    from modal.client import Client

    with enable_output():
        ensure_env(env)
        app = get_app_from_file_contents(file_contents)
        client = Client.from_credentials(token_id, token_secret)
        res = deploy_app(app, name=app_name, client=client, environment_name=env)

    return res.app_id


@app.function(image=modal_helper_image)
def remote_deploy_modal_app(
    file_contents: str, app_name: str, token_id: str, token_secret: str, env: str
):
    return deploy_modal_app(file_contents, app_name, token_id, token_secret, env)
