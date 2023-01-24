import json
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


@app.route('/doi', methods=['POST'])
def mint_doi(event, context, kwargs):
    return {
        'statusCode': 201,
        'body': json.dumps(
            {
                "success": True,
                'message': 'I made a DOI for you. (Not really though, sorry.)',
            })
    }