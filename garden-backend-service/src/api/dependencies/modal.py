from typing import AsyncGenerator

from fastapi import Depends

import modal
from src.config import Settings, get_settings


async def get_modal_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[modal.Client, None]:
    # from_credentials returns an already-started client
    client = await modal.client._Client.from_credentials(
        settings.MODAL_TOKEN_ID, settings.MODAL_TOKEN_SECRET
    )
    try:
        yield client
    finally:
        # Manually close the client since we can't use 'async with' (it would double-open)
        await client.__aexit__(None, None, None)
