import modal
from fastapi import Depends

from src.config import Settings, get_settings
from src.sandboxed_functions.modal_publishing_helpers import (
    deploy_modal_app,
    validate_modal_file,
)


class ValidateModalFileProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        if settings.MODAL_USE_LOCAL:
            self.f = validate_modal_file
        else:
            remote_function = modal.Function.lookup(
                "garden-publishing-helpers",
                "remote_validate_modal_file",
                environment_name=settings.MODAL_ENV,
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
                "garden-publishing-helpers",
                "remote_deploy_modal_app",
                environment_name=settings.MODAL_ENV,
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
