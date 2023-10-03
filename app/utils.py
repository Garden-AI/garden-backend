import os

import boto3


def get_secret(secret_name: str) -> str:
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()

    client = session.client(service_name="secretsmanager", region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    return get_secret_value_response["SecretString"]


def get_environment_from_arn() -> str:
    arn = os.environ["AWS_LAMBDA_FUNCTION_NAME"]

    if "-dev" in arn:
        return "dev"
    elif "-prod" in arn:
        return "prod"
    else:
        raise ValueError("Could not determine correct environment")
