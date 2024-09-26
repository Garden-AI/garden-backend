from fastapi import Depends
from src.config import get_settings, Settings
from src.sandboxed_functions.modal_publishing_helpers import (
    validate_modal_file,
    deploy_modal_app,
)
import modal


class ValidateModalFileProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        if settings.MODAL_USE_LOCAL:
            self.f = validate_modal_file
        else:
            remote_function = modal.Function.lookup(
                "garden-publishing-helpers", "remote_validate_modal_file"
            )
            self.f = remote_function.remote

    def __call__(self, file_contents: str):
        return self.f(file_contents)


class DeployModalAppProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        if settings.MODAL_USE_LOCAL:
            self.f = deploy_modal_app
        else:
            remote_function = modal.Function.lookup(
                "garden-publishing-helpers", "remote_deploy_modal_app"
            )
            self.f = remote_function.remote

    def __call__(
        self,
        file_contents: str,
        app_name: str,
        token_id: str,
        token_secret: str,
        env: str,
    ):
        return self.f(file_contents, app_name, token_id, token_secret, env)
