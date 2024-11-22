from enum import Enum


class AsyncModalJobStatus(Enum):
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"
    TIMED_OUT = "timed_out"
