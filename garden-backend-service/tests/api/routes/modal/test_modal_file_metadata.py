from typing import Any

import pytest

from tests.fixtures.modal_file_constants import (
    INVALID_FUNCTION_KWARGS,
    INVALID_IMAGE_METHOD,
    INVALID_MULTIPLE_APPS,
    INVALID_NO_APP,
    VALID_BASIC_IMPORTS,
    VALID_CLASS_BASED,
    VALID_CONDA_PACKAGES,
    VALID_MULTIPLE_IMAGES,
    VALID_NO_CUSTOM_IMAGE,
)


@pytest.fixture()
def _metadata_validation_fixtures(
    mock_modal_publisher_auth_state,
    mock_db_session,
    override_authenticated_dependency,
    mock_auth_state,
):
    return


def _assert_response_metadata(
    data: dict[str, Any],
    expected_app_name: str,
    expected_function_names: list[str] | None = None,
    expected_requirements: list[str] | None = None,
    expected_conda_requirements: list[str] | None = None,
    expected_base_image: str | None = None,
):
    """Helper to check response data / reduce test boilerplate."""
    assert data["app_name"] == expected_app_name

    if expected_function_names is not None:
        assert all(
            fn in data["modal_function_names"] for fn in expected_function_names
        ), f"{data['modal_function_names']=}"

    if expected_requirements is not None:
        assert all(
            req in data["requirements"] for req in expected_requirements
        ), f"{data['requirements']=}"
    if expected_conda_requirements is not None:
        assert all(
            req in data["conda_requirements"] for req in expected_conda_requirements
        ), f"{data['conda_requirements']=}"
    if expected_base_image is not None:
        assert (
            expected_base_image.lower() in data["base_image_name"].lower()
        ), f"{data['base_image_name']=}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_basic_imports(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": VALID_BASIC_IMPORTS}
    )
    assert response.status_code == 200
    data = response.json()

    _assert_response_metadata(
        data,
        "basic-imports",
        expected_function_names=["number_crunching"],
        expected_requirements=["pandas", "numpy"],
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_no_custom_image(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": VALID_NO_CUSTOM_IMAGE}
    )
    assert response.status_code == 200
    data = response.json()

    _assert_response_metadata(
        data,
        "no-custom-image",
        expected_base_image="python:3.12.6-slim-bookworm",
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_multiple_images(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": VALID_MULTIPLE_IMAGES}
    )
    assert response.status_code == 200
    data = response.json()

    _assert_response_metadata(
        data, "multi-image-app", expected_function_names=["science_stuff", "ml_stuff"]
    )

    for fn_info in data["modal_functions"]:
        if fn_info["function_name"] == "science_stuff":
            assert set(fn_info["requirements"]) == {"numpy", "scipy"}
        elif fn_info["function_name"] == "ml_stuff":
            assert set(fn_info["requirements"]) == {"torch", "transformers"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_class_based(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": VALID_CLASS_BASED}
    )
    assert response.status_code == 200
    data = response.json()

    _assert_response_metadata(
        data,
        "model-app",
        expected_function_names=["Model.predict", "Model.predict_proba"],
    )
    for fn_info in data["modal_functions"]:
        assert "scikit-learn" in fn_info["requirements"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_conda_packages(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": VALID_CONDA_PACKAGES}
    )
    assert response.status_code == 200
    data = response.json()

    _assert_response_metadata(
        data,
        "conda-app",
        expected_conda_requirements=["pytorch", "cudatoolkit"],
        expected_base_image="micromamba",
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_no_app_fails(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": INVALID_NO_APP}
    )
    assert response.status_code == 400
    assert "No Modal App named 'app'" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_multiple_apps_fails(client, _metadata_validation_fixtures):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": INVALID_MULTIPLE_APPS}
    )
    assert response.status_code == 400
    assert "Found 2 App objects" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_invalid_image_method_fails(
    client, _metadata_validation_fixtures
):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": INVALID_IMAGE_METHOD}
    )
    assert response.status_code == 400
    assert "pip_install_from_requirements" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_invalid_function_kwargs_fails(
    client, _metadata_validation_fixtures
):
    response = await client.post(
        "/modal-file-metadata", json={"file_contents": INVALID_FUNCTION_KWARGS}
    )
    assert response.status_code == 400
    assert "secrets" in response.json()["detail"]
