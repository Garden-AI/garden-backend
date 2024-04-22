from pydantic import BaseModel
from ._garden_sdk_schema import _PublishedGarden


class PublishSearchRecordRequest(_PublishedGarden):
    pass


class DeleteSearchRecordRequest(BaseModel):
    doi: str


__all__ = ["PublishSearchRecordRequest", "DeleteSearchRecordRequest"]
