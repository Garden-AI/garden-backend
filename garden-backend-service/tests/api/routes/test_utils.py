import pytest
from fastapi import HTTPException

from src.api.routes._utils import assert_citable
from src.api.schemas.garden import GardenPatchRequest
from src.models.garden import Garden


def test_assert_citable_no_creators():
    garden = Garden(
        title="Test Garden",
        authors=["Test Author"],
        contributors=["Test Contributor"],
    )

    with pytest.raises(HTTPException) as e:
        assert_citable(
            garden,
            GardenPatchRequest(
                authors=[],
                contributors=[],
            ),
        )

    assert e.value.status_code == 409
    assert e.value.detail == "Garden must have at least one author or one contributor"


def test_assert_citable_ignores_valid():
    garden = Garden(
        title="Test Garden",
        authors=["Test Author"],
        contributors=["Test Contributor"],
    )

    # removing the authors should pass since there will be 1 contributor
    assert_citable(garden, GardenPatchRequest(authors=[]))

    # removing the contributors should pass since there will be 1 author
    assert_citable(garden, GardenPatchRequest(contributors=[]))

    # a patch that doesn't update either authors or contributors should pass
    assert_citable(garden, GardenPatchRequest(description="New description"))
