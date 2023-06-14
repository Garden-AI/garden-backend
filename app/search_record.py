import json
import globus_sdk
import boto3

from time import sleep

# garden-dev index
GARDEN_INDEX_UUID = "58e4df29-4492-4e7d-9317-b27eba62a911"


def get_secret():
    secret_name = (
        "arn:aws:secretsmanager:us-east-1:557062710055:secret:garden/globus_api-2YYuTW"
    )
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()

    client = session.client(service_name="secretsmanager", region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    return eval(get_secret_value_response["SecretString"])


def publish(event, _context, _kwargs):
    try:
        globus_secrets = get_secret()
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
        confidential_client, globus_sdk.SearchClient.scopes.resource_server
    )
    search_client = globus_sdk.SearchClient(authorizer=cc_authorizer)

    garden_meta = json.loads(event["body"])

    gmeta_ingest = {
        "subject": garden_meta[
            "uuid"
        ],  # needs to be updated to doi after #140 goes through
        "visible_to": ["all_authenticated_users"],
        "content": garden_meta,
    }

    publish_result = search_client.create_entry(GARDEN_INDEX_UUID, gmeta_ingest)

    max_intervals = 30
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
        sleep(2)
        max_intervals -= 1
        task_result = search_client.get_task(publish_result["task_id"])

    if task_result["state"] == "SUCCESS":
        return {
            "statusCode": 200,
            "body": json.dumps(task_result),
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
