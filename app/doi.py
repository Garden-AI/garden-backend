import json
import logging

import requests
from requests.exceptions import HTTPError
from utils import get_environment_from_arn, get_secret

logger = logging.getLogger()


def get_datacite_secrets() -> dict[str, str]:
    """Build a dict of datacite secrets containing the appropriate dev/prod values"""
    conf = {}
    if get_environment_from_arn() == "dev":
        conf["REPOSITORY_ID"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/repo_id-ePlB1w"
        )
        conf["PASSWORD"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/password-FFLiwt"
        )
        conf["ENDPOINT"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/endpoint-06aepz"
        )
        conf["PREFIX"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/prefix-K6GdzM"
        )
    elif get_environment_from_arn() == "prod":
        # N.B. these are currently identical b/c we don't want to be using the
        # real id/password yet, but we can just update this block as soon as
        # those secrets exist in AWS
        conf["REPOSITORY_ID"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/repo_id-ePlB1w"
        )
        conf["PASSWORD"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/password-FFLiwt"
        )
        conf["ENDPOINT"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/endpoint-06aepz"
        )
        conf["PREFIX"] = get_secret(
            "arn:aws:secretsmanager:us-east-1:557062710055:secret:datacite/prefix-K6GdzM"
        )
    return conf


def call_datacite(event, _context, _kwargs):
    method = event["httpMethod"]
    payload = json.loads(event["body"])
    print(
        f"json {payload = }"
    )  # logger.info appears to not be high enough level to be seen

    datacite_conf = get_datacite_secrets()

    try:
        if method == "POST":
            payload["data"]["attributes"]["prefix"] = datacite_conf["PREFIX"]
            request = requests.post
            target = datacite_conf["ENDPOINT"]
            return_response = {"statusCode": 201}
        elif method == "PUT":
            request = requests.put
            target = f"{datacite_conf['ENDPOINT']}/{payload['data']['attributes']['identifiers'][0]['identifier']}"
            return_response = {"statusCode": 200}
        else:
            return {"statusCode": 400, "body": "Invalid request method."}

        print("making request")
        res: requests.Response = request(
            target,
            headers={"Content-Type": "application/vnd.api+json"},
            json=payload,
            auth=(datacite_conf["REPOSITORY_ID"], datacite_conf["PASSWORD"]),
        )
        print("issued request")
        res.raise_for_status()
    except KeyError as e:
        # failed to set prefix due to malformed payload
        return {"statusCode": 400, "body": str(e)}
    except HTTPError as e:
        # DataCite error responses seem safe to include outright
        # propagate errors from requests.raise_for_status directly
        return {"statusCode": 500, "body": str(e)}
    else:
        # DataCite successful response *would* have all our repo info,
        # so extract just the newly minted DOI for the response body
        print("in epilogue")
        if method == "POST":
            return_response.update(
                body=json.dumps({"doi": res.json()["data"]["attributes"]["doi"]})
            )
        else:
            return_response.update(body="{}")
        return return_response
