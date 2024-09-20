import modal
from fastapi import Depends
from src.config import Settings, get_settings


def get_modal_client(settings: Settings = Depends(get_settings)) -> modal.Client:
    return modal.Client.from_credentials(
        settings.MODAL_TOKEN_ID, settings.MODAL_TOKEN_SECRET
    )
