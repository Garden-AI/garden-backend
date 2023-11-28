import boto3
import json
import hashlib
from utils import get_environment_from_arn


PROD_NOTEBOOK_BUCKET = "pipeline-notebooks-prod"
DEV_NOTEBOOK_BUCKET = "pipeline-notebooks-dev"

def upload_notebook(event, _context, _kwargs):
    bucket = PROD_NOTEBOOK_BUCKET if get_environment_from_arn() == "prod" else DEV_NOTEBOOK_BUCKET
    hash_object = hashlib.sha256(event["body"].encode())
    hash = hash_object.hexdigest()

    # Get the notebook JSON from the request body
    body = json.loads(event["body"])
    notebook_json = body["notebook_json"]
    notebook_name = body["notebook_name"]
    folder = body["folder"] or "misc"
    object_path = f"{folder}/{notebook_name}-{hash}.ipynb"

    # Upload the notebook JSON to S3
    print(f"Uploading notebook to s3://{bucket}/{object_path}")
    s3 = boto3.client("s3")
    s3.put_object(Body=notebook_json, Bucket=bucket, Key=object_path)

    # Generate a public URL for the uploaded notebook
    s3_url = f"https://{bucket}.s3.amazonaws.com/{object_path}"

    return {
        "statusCode": 200,
        "body": json.dumps({"notebook_url": s3_url}),
    }
