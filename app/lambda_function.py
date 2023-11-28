import json

from doi import call_datacite
from search_record import publish
from notebooks import upload_notebook
from tiny_router import TinyLambdaRouter

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


app.route("/doi", methods=["POST", "PUT"])(
    call_datacite
)  # equivalent to decorator syntax
app.route("/garden-search-record", methods=["POST"])(publish)
app.route("/notebook", methods=["POST"])(upload_notebook)
