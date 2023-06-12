import json

from doi import mint_doi, update_metadata
from tiny_router import TinyLambdaRouter

app = TinyLambdaRouter()


def lambda_handler(event, context):
    return app.run(event, context)


@app.route('/hello-world', methods=['GET'])
def hello(event, context, kwargs):
    return {
        'statusCode': 200,
        'body': json.dumps(
            {
                "success": True,
                'message': 'Hello there. You must be an authenticated Globus user.',
            })
    }


app.route("/doi", methods=["POST"])(mint_doi)  # equivalent to decorator syntax
app.route("/doi", methods=["PUT"])(update_metadata)
