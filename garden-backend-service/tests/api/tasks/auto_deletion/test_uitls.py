import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.tasks.auto_deletion.utils import mark_entity_for_deletion
from src.models import Garden, User


async def create_empty_garden(db: AsyncSession) -> Garden:
    user = User(id=1, identity_id="550e8400-e29b-41d4-a716-446655440000")
    db.add(user)

    garden = Garden(
        title="Test Garden",
        doi="some-test/doi-1234",
        authors=[],
        contributors=[],
        tags=[],
        publisher="Garden Test Suite",
        year="2025",
        language="English",
        version="",
        entrypoint_aliases=[],
        user_id=user.id,
    )
    db.add(garden)
    await db.commit()
    return garden


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_marks_gardens_correctly(
    async_db_session,
):
    async with async_db_session() as db:
        test_garden = await create_empty_garden(db)
        await db.commit()
        await mark_entity_for_deletion(Garden, async_db_session)

        assert test_garden.marked_for_deletion is not None
