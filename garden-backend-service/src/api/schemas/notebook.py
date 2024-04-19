from pydantic import BaseModel, HttpUrl, Json, EmailStr


class UploadNotebookRequest(BaseModel):
    notebook_name: str
    notebook_json: Json
    folder: EmailStr  # s3 folder is user's email


class UploadNotebookResponse(BaseModel):
    notebook_url: HttpUrl
