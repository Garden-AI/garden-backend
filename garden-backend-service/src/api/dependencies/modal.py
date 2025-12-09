import asyncio
from typing import Optional

import structlog
from fastapi import Depends

import modal
from src.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class ModalClient:
    """Singleton wrapper for modal.Client to prevent resource leaks."""

    _instance: Optional["ModalClient"] = None
    _client: Optional[modal.Client] = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "ModalClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_client(self, settings: Settings) -> modal.Client:
        # Double-checked locking optimization
        if self._client is not None:
            return self._client

        async with self._lock:
            # Check again after acquiring lock
            if self._client is None:
                logger.info("Initializing new Modal client singleton...")
                # Create and enter the client context
                client = modal.client._Client.from_credentials(
                    settings.MODAL_TOKEN_ID, settings.MODAL_TOKEN_SECRET
                )
                # We need to explicitly enter the context to keep it alive
                self._client = await client.__aenter__()
                logger.info("Modal client singleton initialized successfully")
            return self._client


async def get_modal_client(settings: Settings = Depends(get_settings)) -> modal.Client:
    return await ModalClient.get_instance().get_client(settings)
