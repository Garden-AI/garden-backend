import json

from doi import call_datacite
from search_record import publish_search_record, delete_search_record
from notebooks import upload_notebook
from tiny_router import TinyLambdaRouter
from ecr_token import create_ecr_sts_token

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
                "message": "Hello there. You must be World. I'm a huge fan of your work.",
            }
        ),
    }


app.route("/doi", methods=["POST", "PUT"])(call_datacite)
app.route("/garden-search-record", methods=["POST"])(publish_search_record)
app.route("/garden-search-record", methods=["DELETE"])(delete_search_record)
app.route("/notebook", methods=["POST"])(upload_notebook)
app.route("/docker-push-token", methods=["GET"])(create_ecr_sts_token)
