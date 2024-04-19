import boto3
import json
import hashlib
from fastapi import APIRouter, Depends, status
from src.config import Settings, get_settings

from src.api.dependencies.auth import AuthenticationState, authenticated
from src.api.schemas.notebook import UploadNotebookRequest, UploadNotebookResponse

router = APIRouter(prefix="/notebook")


@router.post("/", status_code=status.HTTP_200_OK)
async def upload_notebook(
    body: UploadNotebookRequest,
    settings: Settings = Depends(get_settings),
    auth: AuthenticationState = Depends(authenticated),
) -> UploadNotebookResponse:
    # make sure we're writing to the right folder
    if auth.username != body.folder:
        raise Exception()

    raw_payload: bytes = body.json().encode()
    hash_object = hashlib.sha256(raw_payload)
    hash = hash_object.hexdigest()

    object_path = f"{body.folder}/{body.notebook_name}-{hash}.ipynb"

    s3 = boto3.client("s3")
    s3.put_object(
        Body=json.dumps(body.notebook_json),
        Bucket=settings.NOTEBOOKS_S3_BUCKET,
        Key=object_path,
    )

    s3_url = f"https://{settings.NOTEBOOKS_S3_BUCKET}.s3.amazonaws.com/{object_path}"
    return UploadNotebookResponse(notebook_url=s3_url)
