import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_draft_gardens_marked_for_deletion():
    """Tests that gardens in a draft state are tagged for auto deletion"""
    pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_modal_apps_marked_for_deletion_if_unused():
    """Tests that modal apps are tagged for auto deletion if their functions are not used"""
    pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_entities_marked_for_deletion_are_deleted():
    """Tests that gardens/modal-apps marked for deletion are actually deleted"""
    pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_modal_apps_marked_for_deletion_are_unmarked_if_used():
    """Tests that modal apps tagged for auto deletion are un-tagged if they are used by a garden"""
    pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gardens_marked_for_deletion_are_unmarked_if_published():
    """Tests that gardens tagged for auto deletion are un-tagged if they are published"""
    pass
