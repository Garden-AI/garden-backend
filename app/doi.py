import os
import json

import requests
from requests.exceptions import HTTPError

import logging

logger = logging.getLogger()


def mint_doi(event, _context, _kwargs):
    payload = json.loads(event["body"])
    try:
        DATACITE_REPOSITORY_ID = os.environ["DATACITE_REPOSITORY_ID"]
        DATACITE_PASSWORD = os.environ["DATACITE_PASSWORD"]
        DATACITE_ENDPOINT = os.environ["DATACITE_ENDPOINT"]
        DATACITE_PREFIX = os.environ["DATACITE_PREFIX"]
    except KeyError as e:
        message = (
            "Garden server was unable to authenticate with DataCite. Please "
            "contact support and/or open an issue at "
            "https://github.com/Garden-AI/garden-backend/issues. "
        )
        logger.error(f"DATACITE_* environment variables not set. env: {os.environ}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": message, "error": str(e)}),
        }
    try:
        payload["data"]["attributes"]["prefix"] = DATACITE_PREFIX

        res: requests.Response = requests.post(
            DATACITE_ENDPOINT,
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
        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "doi": res.json()["data"]["attributes"]["doi"],
                }
            ),
        }
