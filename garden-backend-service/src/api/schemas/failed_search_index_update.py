from datetime import datetime

from .base import BaseSchema


class FailedSearchIndexUpdateResponse(BaseSchema):
    doi: str
    operation_type: str
    error_message: str
    retry_count: int
    last_attempt: datetime
