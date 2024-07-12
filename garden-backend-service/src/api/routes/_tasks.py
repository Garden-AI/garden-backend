from src.api.dependencies.search import get_globus_search_client
from src.auth.globus_auth import get_auth_client
from src.config import Settings
from src.models import Garden

from ._utils import _garden_sqlalchemy_to_pydantic, poll_globus_search_task


async def delete_from_search_index(garden: Garden, settings: Settings):
    client = get_globus_search_client(get_auth_client())
    delete_result = client.delete_entry(
        settings.GLOBUS_SEARCH_INDEX_ID,
        garden.doi,
    )
    task_id = delete_result["task_id"]
    return await poll_globus_search_task(task_id, client)


async def create_or_update_on_search_index(garden: Garden, settings: Settings):
    client = get_globus_search_client(get_auth_client())
    garden_pub = _garden_sqlalchemy_to_pydantic(garden)
    garden_meta = {
        "subject": garden_pub.doi,
        "visible_to": ["public"],
        "content": garden_pub.dict(),
    }
    create_result = client.create_entry(
        settings.GLOBUS_SEARCH_INDEX_ID,
        garden_meta,
    )
    task_id = create_result["task_id"]

    return await poll_globus_search_task(task_id, client)
