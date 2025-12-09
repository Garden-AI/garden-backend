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

    async def reset(self):
        """Resets the singleton instance, forcing a fresh client on next access."""
        async with self._lock:
            if self._client:
                logger.info("Resetting Modal client singleton...")
                try:
                    # Attempt to gracefully close the existing client
                    await self._client.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Error closing Modal client during reset: {e}")
                finally:
                    # Always ensure client is cleared so next request creates a new one
                    self._client = None
                    logger.info("Modal client singleton reset complete")


async def get_modal_client(settings: Settings = Depends(get_settings)) -> modal.Client:
    return await ModalClient.get_instance().get_client(settings)
