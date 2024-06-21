import hashlib
import json
import pytest
from unittest.mock import patch

from src.api.schemas.notebook import UploadNotebookRequest


@pytest.mark.asyncio
async def test_upload_notebook(
    client,
    override_authenticated_dependency,
    override_get_settings_dependency,
):
    request_data = dict(
        notebook_name="test_notebook",
        notebook_json=json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "interlinked",
                        "within_cells": "interlinked",
                        "source": "print('dreadfully distinct')",
                    }
                ]
            }
        ),
        folder="Monsieur.Sartre@ens-paris.fr",  # not a commentary on nabokov, just needs to match the auth mock
    )
    request_obj = UploadNotebookRequest(**request_data)
    test_hash = hashlib.sha256(request_obj.json().encode()).hexdigest()

    with patch("boto3.client") as mock_boto_client:
        mock_s3 = mock_boto_client.return_value
        response = await client.post("/notebook", json=request_data)

        assert response.status_code == 200
        assert (
            "test-bucket.s3.amazonaws.com/Monsieur.Sartre@ens-paris.fr"
            in response.json()["notebook_url"]
        )
        mock_s3.put_object.assert_called_once_with(
            Body=request_data["notebook_json"],
            Bucket="test-bucket",
            Key=f"{request_obj.folder}/{request_obj.notebook_name}-{test_hash}.ipynb",
        )

    return
