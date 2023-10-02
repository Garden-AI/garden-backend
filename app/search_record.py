import json
from time import sleep

import globus_sdk
from utils import get_environment_from_arn, get_secret

# garden-dev index
DEV_INDEX = "58e4df29-4492-4e7d-9317-b27eba62a911"
PROD_INDEX = "813d4556-cbd4-4ba9-97f2-a7155f70682f"
GARDEN_INDEX_UUID = (
    PROD_INDEX if get_environment_from_arn() == "prod" else DEV_INDEX
)


def publish(event, _context, _kwargs):
    try:
        globus_secrets = json.loads(
            get_secret(
                "arn:aws:secretsmanager:us-east-1:557062710055:secret:garden/globus_api-2YYuTW"
            )
        )
    except Exception:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Server encountered an error acquiring credentials"}
            ),
        }

    confidential_client = globus_sdk.ConfidentialAppAuthClient(
        globus_secrets["API_CLIENT_ID"], globus_secrets["API_CLIENT_SECRET"]
    )
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(
        confidential_client, globus_sdk.SearchClient.scopes.all
    )
    search_client = globus_sdk.SearchClient(authorizer=cc_authorizer)

    garden_meta = json.loads(event["body"])

    gmeta_ingest = {
        "subject": garden_meta["doi"],
        "visible_to": ["public"],
        "content": garden_meta,
    }

    publish_result = search_client.create_entry(GARDEN_INDEX_UUID, gmeta_ingest)

    max_intervals = 25
    task_result = search_client.get_task(publish_result["task_id"])
    while task_result["state"] not in {"FAILED", "SUCCESS"}:
        if not max_intervals:
            return {
                "statusCode": 408,
                "body": json.dumps(
                    {
                        "message": f"Server timed out waiting for publish task to finish, you can manually check its progress with the task id: {task_result['task_id']}"
                    }
                ),
            }
        sleep(0.2)
        max_intervals -= 1
        task_result = search_client.get_task(publish_result["task_id"])

    if task_result["state"] == "SUCCESS":
        return {
            "statusCode": 200,
            "body": "{}",
        }
    else:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": f"The publication process failed. Globus responded with: {task_result['fatal_error']}"
                },
            ),
        }
