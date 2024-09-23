from fastapi import Depends
from src.config import get_settings, Settings
from src.sandboxed_functions.modal_publishing_helpers import (
    validate_modal_file, 
    deploy_modal_app,
    remote_deploy_modal_app,
    remote_validate_modal_file
)

class ValidateModalFileProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        self.settings = settings

    def __call__(self, file_contents: str):
        f = validate_modal_file if self.settings.MODAL_USE_LOCAL else remote_validate_modal_file.remote
        return f(file_contents)

class DeployModalAppProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        self.settings = settings

    def __call__(self, file_contents: str, app_name: str, token_id: str, token_secret: str, env: str):
        f = deploy_modal_app if self.settings.MODAL_USE_LOCAL else remote_deploy_modal_app.remote
        return deploy_modal_app(file_contents, app_name, token_id, token_secret, env)
