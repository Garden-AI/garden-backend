import json

import logging
import boto3

logger = logging.getLogger()

EXPIRATION_TIME = 3600  # 3600 seconds == 1 hour
UPLOAD = "upload"
DOWNLOAD = "download"


def make_upload_url(full_object_path: str, bucket: str) -> dict:
    s3 = boto3.client("s3")
    return s3.generate_presigned_post(
        bucket, full_object_path, Fields=None, Conditions=None, ExpiresIn=EXPIRATION_TIME
    )


def make_download_url(full_object_path: str, bucket: str) -> dict:
    s3 = boto3.client("s3")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": full_object_path},
        ExpiresIn=EXPIRATION_TIME,
    )
    return {
        "url": url
    }


url_makers = {
    UPLOAD: make_upload_url,
    DOWNLOAD: make_download_url
}


def make_presigned_url(event, _context, _kwargs):
    bucket_name = "garden-mlflow-models-dev"
    payload = json.loads(event["body"])
    batch = payload["batch"]
    direction = payload["direction"]
    responses = []

    if direction not in url_makers:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": f"'direction' must be one of {UPLOAD} or {DOWNLOAD}. Got {direction}"}),
        }

    for s3_path in batch:
        if not is_probably_valid_object_path(s3_path):
            message = "'s3_path' must be formatted like '<email address>/<model short name>/model.zip'. "
            message += f"Got {s3_path}"
            return {
                "statusCode": 400,
                "body": json.dumps({"message": message}),
            }

        make_url = url_makers[direction]
        try:
            url_and_fields_payload = make_url(s3_path, bucket_name)
        except Exception as e:
            return {"statusCode": 500, "body": str(e)}

        responses.append({"body": json.dumps(url_and_fields_payload)})

    # provides all of the responses when successful, otherwise only the first error encountered
    return {"statusCode": 200, "body": json.dumps({"responses": responses})}


def is_probably_valid_object_path(object_path: str):
    """
    This is not meant to be rigorous, it's just to prevent obvious mistakes.
    Should look like "email@address.edu/model-name/model.zip"
    Returns True if it is not obviously malformed. False if it is.

    :param object_path: The path we have gotten a request to generate a URL for.
    :return: bool
    """
    segments = object_path.split("/")
    if len(segments) != 3:
        return False

    if segments[2] != "model.zip":
        return False

    if "@" not in segments[0]:
        return False

    return True
