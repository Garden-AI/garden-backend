from typing import AsyncGenerator

from fastapi import Depends

import modal
from src.config import Settings, get_settings


async def get_modal_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[modal.Client, None]:
    client = await modal.client._Client.from_credentials(
        settings.MODAL_TOKEN_ID, settings.MODAL_TOKEN_SECRET
    )
    async with client:
        yield client
