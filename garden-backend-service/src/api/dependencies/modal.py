from fastapi import Depends

import modal
from src.config import Settings, get_settings


async def get_modal_client(settings: Settings = Depends(get_settings)) -> modal.Client:
    return await modal.client._Client.from_credentials(
        settings.MODAL_TOKEN_ID, settings.MODAL_TOKEN_SECRET
    )
