from src.api.dependencies.search import get_globus_search_client
from src.auth.globus_auth import get_auth_client
from src.config import Settings

from ._utils import poll_globus_search_task


async def delete_from_search_index(garden_data, settings: Settings):
    if settings.SYNC_SEARCH_INDEX:
        client = get_globus_search_client(get_auth_client())
        delete_result = client.delete_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_data.doi,
        )
        task_id = delete_result["task_id"]
        return await poll_globus_search_task(task_id, client)


async def create_or_update_on_search_index(garden_data, settings: Settings):
    if settings.SYNC_SEARCH_INDEX:
        client = get_globus_search_client(get_auth_client())
        create_result = client.create_entry(
            settings.GLOBUS_SEARCH_INDEX_ID,
            garden_data.doi,
        )
        task_id = create_result["task_id"]

        return await poll_globus_search_task(task_id, client)
