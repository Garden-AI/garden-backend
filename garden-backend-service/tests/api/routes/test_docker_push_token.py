from unittest.mock import patch

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_push_session(
    client,
    override_get_settings_dependency,
    override_authenticated_dependency,
):
    mock_assume_role = {
        "Credentials": {
            "AccessKeyId": "testAccessKey",
            "SecretAccessKey": "testSecretKey",
            "SessionToken": "testSessionToken",
        }
    }

    with patch("boto3.client") as mock_client:
        client_instance = mock_client.return_value
        client_instance.assume_role.return_value = mock_assume_role

        response = await client.get("/docker-push-token/", follow_redirects=True)

    assert response.status_code == 200
    assert response.json() == {
        "AccessKeyId": "testAccessKey",
        "SecretAccessKey": "testSecretKey",
        "SessionToken": "testSessionToken",
        "ECRRepo": "ECR_REPO_ARN",
        "RegionName": "us-east-1",
    }

    for key in ["AccessKeyId", "SecretAccessKey", "SessionToken", "ECRRepo"]:
        assert key in response.json()
