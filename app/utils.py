import json
import boto3

from typing import Union


def get_secret(secret_name: str) -> Union[dict, str]:
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()

    client = session.client(service_name="secretsmanager", region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    # some of our secrets are stored as str(dict[str, str]), and others are just strings
    try:
        print(f"Trying to json.loads {secret_name}")
        return json.loads(get_secret_value_response["SecretString"])
    except json.JSONDecodeError:
        print(f"Trying to get {secret_name} raw")
        return get_secret_value_response["SecretString"]
