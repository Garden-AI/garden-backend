from fastapi import Depends
from src.config import get_settings, Settings
from src.sandboxed_functions.modal_publishing_helpers import (
    validate_modal_file, 
    deploy_modal_app,
    remote_deploy_modal_app,
    remote_validate_modal_file
)

def get_validate_modal_file(settings: Settings = Depends(get_settings)):
    return validate_modal_file if settings.MODAL_USE_LOCAL else remote_validate_modal_file.remote

def get_deploy_modal_app(settings: Settings = Depends(get_settings)):
    return deploy_modal_app if settings.MODAL_USE_LOCAL else remote_deploy_modal_app.remote