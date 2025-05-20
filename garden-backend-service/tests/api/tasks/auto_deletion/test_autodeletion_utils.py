import asyncio
from datetime import datetime, timedelta

import pytest
from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.tasks.auto_deletion.utils import (
    delete_marked_entity,
    mark_entity_for_deletion,
    unmark_marked_gardens,
    unmark_marked_modal_apps,
)
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
        unpublished_garden = await create_empty_garden(db)
        # since the garden is not published, this modal app should get marked
        unpublished_garden.modal_functions = used_modal_app.modal_functions

        # create a second garden that is publised
        published_garden = await create_empty_garden(db, draft=False)
        # add another modal app that is used by the published garden, this one should not get marked
        pub_modal_app = await create_modal_app_with_functions(db)
        published_garden.modal_functions = pub_modal_app.modal_functions

        await db.commit()
        await db.refresh(published_garden)
        await db.refresh(unpublished_garden)
        await db.refresh(used_modal_app)
        await db.refresh(pub_modal_app)

        # run the marking task
        num_marked = await mark_entity_for_deletion(ModalApp, async_db_session)
        assert num_marked == 2

        await db.refresh(unused_modal_app)
        await db.refresh(used_modal_app)
        await db.refresh(pub_modal_app)

        assert unused_modal_app.marked_for_deletion is not None
        assert (
            used_modal_app.marked_for_deletion is not None
        )  # this one should be marked since it is only used by unpublished gardens
        assert (
            pub_modal_app.marked_for_deletion is None
        )  # we shouldn't mark apps that are used by published gardens


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_is_idempotent(async_db_session):
    async with async_db_session() as db:
        garden = await create_empty_garden(db)

        num_marked = await mark_entity_for_deletion(Garden, async_db_session)
        assert num_marked == 1

        await db.refresh(garden)
        assert garden.marked_for_deletion is not None
        marked_time = garden.marked_for_deletion

        num_marked_second_time = await mark_entity_for_deletion(
            Garden, async_db_session
        )
        assert num_marked_second_time == 0
        await db.refresh(garden)
        assert (
            garden.marked_for_deletion == marked_time
        )  # marked time should not have changed, or been removed


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmark_marked_gardens_unmarks_published_gardens(
    async_db_session,
):
    async with async_db_session() as db:
        # create a published garden
        garden = await create_empty_garden(db, draft=False)
        # simulate that it was previously marked for deltion
        garden.marked_for_deletion = datetime.now()
        await db.commit()

        # run the unmarking function
        num_unmarked = await unmark_marked_gardens(async_db_session)
        assert num_unmarked == 1

        await db.refresh(garden)
        assert garden.marked_for_deletion is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmark_marked_gardens_ignores_unpublished_gardens(
    async_db_session,
):
    async with async_db_session() as db:
        # create an unpublished garden
        garden = await create_empty_garden(db)
        # simulate that it was previously marked for deltion
        garden.marked_for_deletion = datetime.now()
        await db.commit()

        # run the unmarking function
        num_unmarked = await unmark_marked_gardens(async_db_session)
        assert num_unmarked == 0

        await db.refresh(garden)
        # make sure the garden is still marked
        assert garden.marked_for_deletion is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmark_marked_modal_apps_unmarks_used_apps(
    async_db_session,
):
    async with async_db_session() as db:
        # create a published garden
        garden = await create_empty_garden(db, draft=False)
        # create a modal app
        modal_app = await create_modal_app_with_functions(db)
        # simulate that it was marked for deletion at some point
        modal_app.marked_for_deletion = datetime.now()
        # it is now in-use by the garden:
        garden.modal_functions = modal_app.modal_functions

        # create an unused modal app, this one should stay marked
        unused_app = await create_modal_app_with_functions(db)
        unused_app.marked_for_deletion = datetime.now()
        await db.commit()

        # run the unmarking function
        num_unmarked = await unmark_marked_modal_apps(async_db_session)
        assert num_unmarked == 1

        await db.refresh(modal_app)
        await db.refresh(unused_app)
        assert modal_app.marked_for_deletion is None  # should have been unmarked
        assert unused_app.marked_for_deletion is not None  # should have stayed marked


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_marked_entites_deletes_marked_objects_when_past_limit(
    async_db_session,
    override_get_modal_client_dependency,
    mocker,
    mock_settings,
):
    # Patch the get_settings function to return our mock settings
    mocker.patch(
        "src.api.tasks.auto_deletion.utils.get_settings", return_value=mock_settings
    )

    # Directly mock the stop_modal_app function to succeed
    mock_stop_app = mocker.patch("src.api.tasks.auto_deletion.utils.stop_modal_app")

    async with async_db_session() as db:
        garden = await create_empty_garden(db)
        garden.marked_for_deletion = datetime.now()
        unmarked_garden = await create_empty_garden(db)

        modal_app = await create_modal_app_with_functions(db)
        modal_app.app_name = "test-app"
        modal_app.modal_app_id = "test-app-id"
        modal_app.marked_for_deletion = datetime.now()

        unmarked_modal_app = await create_modal_app_with_functions(db)
        await db.commit()

        # set the deletion interval to something short
        interval = timedelta(milliseconds=100)
        # wait a bit longer than the interval to make sure the marked obejcts will be deleted
        await asyncio.sleep(0.2)
        num_gardens_deleted = await delete_marked_entity(
            Garden, async_db_session, interval
        )
        num_apps_deleted = await delete_marked_entity(
            ModalApp, async_db_session, interval, override_get_modal_client_dependency
        )

        assert num_gardens_deleted == 1
        assert num_apps_deleted == 1
        # Verify the stop_modal_app function was called
        assert mock_stop_app.called

        # Query for deleted garden and modal_app by id
        deleted_garden_result = await db.execute(
            select(Garden).where(Garden.id == garden.id)
        )
        deleted_garden = deleted_garden_result.scalar_one_or_none()
        deleted_modal_app_result = await db.execute(
            select(ModalApp).where(ModalApp.id == modal_app.id)
        )
        deleted_modal_app = deleted_modal_app_result.scalar_one_or_none()

        # Query for unmarked (should still exist)
        unmarked_garden_result = await db.execute(
            select(Garden).where(Garden.id == unmarked_garden.id)
        )
        unmarked_garden_db = unmarked_garden_result.scalar_one_or_none()
        unmarked_modal_app_result = await db.execute(
            select(ModalApp).where(ModalApp.id == unmarked_modal_app.id)
        )
        unmarked_modal_app_db = unmarked_modal_app_result.scalar_one_or_none()

        assert deleted_garden is None
        assert deleted_modal_app is None
        assert unmarked_garden_db is not None
        assert unmarked_modal_app_db is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_marked_entities_skips_if_not_past_interval(
    async_db_session,
    override_get_modal_client_dependency,
    mocker,
    mock_settings,
):
    # Patch the get_settings function to return our mock settings
    mocker.patch(
        "src.api.tasks.auto_deletion.utils.get_settings", return_value=mock_settings
    )

    # Directly mock the stop_modal_app function again
    mock_stop_app = mocker.patch("src.api.tasks.auto_deletion.utils.stop_modal_app")

    async with async_db_session() as db:
        garden = await create_empty_garden(db)
        garden.marked_for_deletion = datetime.now()

        modal_app = await create_modal_app_with_functions(db)
        modal_app.app_name = "test-app"
        modal_app.modal_app_id = "test-app-id"
        modal_app.marked_for_deletion = datetime.now()
        await db.commit()

        # Use a large interval so the entities are not old enough to be deleted
        interval = timedelta(hours=1)
        num_gardens_deleted = await delete_marked_entity(
            Garden, async_db_session, interval
        )
        num_apps_deleted = await delete_marked_entity(
            ModalApp, async_db_session, interval, override_get_modal_client_dependency
        )

        assert num_gardens_deleted == 0
        assert num_apps_deleted == 0
        # The stop app function should not be called in this case
        assert not mock_stop_app.called

        # Confirm both objects still exist
        garden_result = await db.execute(select(Garden).where(Garden.id == garden.id))
        garden_db = garden_result.scalar_one_or_none()
        modal_app_result = await db.execute(
            select(ModalApp).where(ModalApp.id == modal_app.id)
        )
        modal_app_db = modal_app_result.scalar_one_or_none()
        assert garden_db is not None
        assert modal_app_db is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mark_entities_for_deletion_deletes_apps_in_archived_gardens(
    async_db_session,
):
    async with async_db_session() as db:
        archived_garden = await create_empty_garden(db, draft=False)
        archived_garden.is_archived = True
        modal_app = await create_modal_app_with_functions(db)
        archived_garden.modal_functions = modal_app.modal_functions
        await db.commit()

        await db.refresh(archived_garden)
        await db.refresh(modal_app)

        num_marked_apps = await mark_entity_for_deletion(ModalApp, async_db_session)
        assert num_marked_apps == 1

        await db.refresh(archived_garden)
        await db.refresh(modal_app)
        assert modal_app.marked_for_deletion is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_garden_unmarking_function_doesnt_undo_marking_function(
    async_db_session,
):
    """Tests that the garden unmarking function doens't immediately undo the marking function"""
    async with async_db_session() as db:
        garden = await create_empty_garden(db)

        num_marked = await mark_entity_for_deletion(Garden, async_db_session)
        assert num_marked == 1

        num_unmarked = await unmark_marked_gardens(async_db_session)
        assert num_unmarked == 0

        await db.refresh(garden)
        assert garden.marked_for_deletion is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_app_unmarking_function_doesnt_undo_marking_function(
    async_db_session,
):
    """Tests that the modal app unmarking function doens't immediately undo the marking function"""
    async with async_db_session() as db:
        modal_app = await create_modal_app_with_functions(db)

        num_marked = await mark_entity_for_deletion(ModalApp, async_db_session)
        assert num_marked == 1

        num_unmarked = await unmark_marked_modal_apps(async_db_session)
        assert num_unmarked == 0

        await db.refresh(modal_app)
        assert modal_app.marked_for_deletion is not None
