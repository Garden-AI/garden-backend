import json
import globus_sdk

from time import sleep
from doi import call_datacite
from tiny_router import TinyLambdaRouter
from authorizer.lambda_function import get_secret

# garden-dev index
GARDEN_INDEX_UUID = "58e4df29-4492-4e7d-9317-b27eba62a911"
app = TinyLambdaRouter()


def lambda_handler(event, context):
    return app.run(event, context)


@app.route("/hello-world", methods=["GET"])
def hello(event, context, kwargs):
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "success": True,
                "message": "Hello there. You must be an authenticated Globus user.",
            }
        ),
    }


@app.route("/publish", methods=["POST"])
def publish(event, context, kwargs):
    globus_secrets = get_secret()

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

    task_result = search_client.get_task(publish_result["task_id"])
    while not task_result["state"] in {"FAILED", "SUCCESS"}:
        sleep(5)  # is this bad practice?
        task_result = search_client.get_task(publish_result["task_id"])

    return {"statusCode": 200, "body": json.dumps(task_result)}  # should the statusCode be chosen using task status? (and how to choose 4XX vs. 5XX)


app.route("/doi", methods=["POST", "PUT"])(call_datacite)  # equivalent to decorator syntax
