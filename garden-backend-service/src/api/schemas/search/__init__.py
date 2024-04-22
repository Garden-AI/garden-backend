from pydantic import BaseModel
from ._garden_sdk_schema import _PublishedGarden as PublishSearchRecordRequest


class DeleteSearchRecordRequest(BaseModel):
    doi: str


__all__ = ["PublishSearchRecordRequest", "DeleteSearchRecordRequest"]
