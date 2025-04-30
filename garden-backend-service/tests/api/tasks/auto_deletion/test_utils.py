import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.tasks.auto_deletion.utils import mark_entity_for_deletion
from src.modal.status import AsyncModalJobStatus
from src.models import Garden, ModalApp, ModalFunction, User

fake = Faker()


async def create_fake_user(db: AsyncSession) -> User:
    user = User(identity_id=fake.uuid4())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_empty_garden(db: AsyncSession, draft: bool = True) -> Garden:
    user = await create_fake_user(db)
    garden = Garden(
        title="Test Garden",
        doi=fake.doi(),
        doi_is_draft=draft,
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
    await db.refresh(garden)
    return garden


async def create_modal_function(modal_app: ModalApp, db: AsyncSession) -> ModalFunction:
    modal_function = ModalFunction(
        title=fake.name(),
        authors=[],
        tags=[],
        year="2025",
        function_name=fake.name(),
        function_text=fake.text(),
        hardware_spec={},
        test_functions=[],
        modal_app_id=modal_app.id,
    )
    db.add(modal_function)
    await db.commit()
    await db.refresh(modal_function)
    return modal_function


async def create_modal_app_with_functions(
    db: AsyncSession, num_functions: int = 2, used_by: Garden | None = None
) -> ModalApp:
    user = await create_fake_user(db)
    modal_app = ModalApp(
        app_name=fake.uuid4(),
        original_app_name=fake.name(),
        base_image_name=fake.name(),
        file_contents=fake.text(),
        requirements=[],
        deploy_status=AsyncModalJobStatus.DONE,
        user_id=user.id,
    )
    db.add(modal_app)
    await db.commit()
    await db.refresh(modal_app)

    for _ in range(num_functions):
        _ = await create_modal_function(modal_app, db)

    await db.refresh(modal_app)
    return modal_app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_marks_draft_gardens(
    async_db_session,
):
    async with async_db_session() as db:
        test_garden = await create_empty_garden(db)
        # The doi should be draft, and not marked for deletion
        assert test_garden.doi_is_draft
        assert test_garden.marked_for_deletion is None

        # Run the marking function
        num_marked = await mark_entity_for_deletion(Garden, async_db_session)
        assert num_marked == 1

        # Refresh and see if it was marked!
        await db.refresh(test_garden)
        assert test_garden.marked_for_deletion is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_ignores_published_gardens(
    async_db_session,
):
    async with async_db_session() as db:
        unpublished_garden = await create_empty_garden(db)
        published_garden = await create_empty_garden(db, draft=False)

        num_marked = await mark_entity_for_deletion(Garden, async_db_session)
        assert num_marked == 1  # we marked the unpublished garden

        await db.refresh(unpublished_garden)
        await db.refresh(published_garden)
        assert unpublished_garden.marked_for_deletion is not None
        assert (
            published_garden.marked_for_deletion is None
        )  # we should have ignored the published garden


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_marks_unused_modal_apps(
    async_db_session,
):
    async with async_db_session() as db:
        modal_app = await create_modal_app_with_functions(db)
        assert modal_app.marked_for_deletion is None

        num_marked = await mark_entity_for_deletion(ModalApp, async_db_session)
        assert num_marked == 1

        await db.refresh(modal_app)
        assert modal_app.marked_for_deletion is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_ignores_in_use_modal_apps(
    async_db_session,
):
    async with async_db_session() as db:
        # create a couple of modal apps and a garden using one of them
        unused_modal_app = await create_modal_app_with_functions(db)
        used_modal_app = await create_modal_app_with_functions(db)
        garden = await create_empty_garden(db)
        garden.modal_functions = used_modal_app.modal_functions
        await db.commit()
        await db.refresh(used_modal_app)

        # run the marking task
        num_marked = await mark_entity_for_deletion(ModalApp, async_db_session)
        assert num_marked == 1

        await db.refresh(unused_modal_app)
        await db.refresh(used_modal_app)

        assert unused_modal_app.marked_for_deletion is not None
        assert used_modal_app.marked_for_deletion is None
