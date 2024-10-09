from unittest.mock import MagicMock

import pytest

from src.auth.globus_groups import add_user_to_group


@pytest.mark.asyncio
async def test_add_user_to_group(
    mocker,
    mock_auth_state,
    mock_settings,
):
    module = "src.auth.globus_groups"

    mock_groups_manager = MagicMock()
    mocker.patch(
        module + "._create_service_groups_manager",
        return_value=mock_groups_manager,
    )

    add_user_to_group(mock_auth_state, mock_settings)

    # Verify the user was added to the group
    mock_groups_manager.add_member.assert_called_once_with(
        mock_settings.GARDEN_USERS_GROUP_ID,
        mock_auth_state.identity_id,
    )
