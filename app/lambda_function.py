import json

def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps(
            {
                "success": True,
                'message': 'hello traveler, take a look at my wares',
                'dabloons': 5
            })
    }