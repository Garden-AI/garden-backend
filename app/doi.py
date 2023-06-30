import json

import requests
from requests.exceptions import HTTPError
from utils import get_secret

import logging

logger = logging.getLogger()


def call_datacite(event, _context, _kwargs):
    method = event["httpMethod"]
    payload = json.loads(event["body"])
    print(f"json {payload = }")  # logger.info appears to not be high enough level to be seen

    DATACITE_REPOSITORY_ID = get_secret("REPO-ID-SECRETLOC-HERE")
    DATACITE_PASSWORD = get_secret("DATACITE-PWD-SECRETLOC-HERE")
    DATACITE_ENDPOINT = get_secret("DATACITE-ENDPOINT-SECRETLOC-HERE")
    DATACITE_PREFIX = get_secret("DATACITE-PREFIX-SECRETLOC-HERE")

    try:
        if method == "POST":
            payload["data"]["attributes"]["prefix"] = DATACITE_PREFIX
            request = requests.post
            target = DATACITE_ENDPOINT
            return_response = {"statusCode": 201}
        elif method == "PUT":
            request = requests.put
            target = f"{DATACITE_ENDPOINT}/{payload['data']['attributes']['identifiers'][0]['identifier']}"
            return_response = {"statusCode": 200}
        else:
            return {"statusCode": 400, "body": "Invalid request method."}

        res: requests.Response = request(
            target,
            headers={"Content-Type": "application/vnd.api+json"},
            json=payload,
            auth=(DATACITE_REPOSITORY_ID, DATACITE_PASSWORD),
        )
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
        if method == "POST":
            return_response.update(
                body=json.dumps({"doi": res.json()["data"]["attributes"]["doi"]})
            )
        else:
            return_response.update(body="{}")
        return return_response
