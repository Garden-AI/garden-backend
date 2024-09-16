import logging
import sys

import structlog

# naive config for built-in logger that plays nice with structlog
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

# reset log level to warning for chatty libraries
for module in ["globus_sdk", "urllib3", "fastapi", "uvicorn", "boto3"]:
    logging.getLogger(module).setLevel(logging.WARNING)

# see: https://www.structlog.org/en/stable/standard-library.html
structlog.configure(
    processors=[
        # ensures that objects returned from get_logger() share context within a given request
        structlog.contextvars.merge_contextvars,
        # If log level is too low, abort pipeline and throw away log entry.
        structlog.stdlib.filter_by_level,
        # Add log level to event dict.
        structlog.stdlib.add_log_level,
        # Add a timestamp in ISO 8601 format.
        structlog.processors.TimeStamper(fmt="iso"),
        # If the "stack_info" key in the event dict is true, remove it and
        # render the current stack trace in the "stack" key.
        structlog.processors.StackInfoRenderer(),
        # add function name to log
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
        # If the "exc_info" key in the event dict is either true or a
        # sys.exc_info() tuple, remove "exc_info" and render the exception
        # with traceback into the "exception" key.
        structlog.processors.format_exc_info,
        # If some value is in bytes, decode it to a Unicode str.
        structlog.processors.UnicodeDecoder(),
        # Render the final event dict
        structlog.processors.LogfmtRenderer(
            sort_keys=True,
            key_order=["event", "level", "status_code"],
            bool_as_flag=False,
            drop_missing=True,
        ),
    ],
    # `wrapper_class` is the bound logger that you get back from
    # get_logger(). This one imitates the API of `logging.Logger`.
    wrapper_class=structlog.stdlib.BoundLogger,
    # `logger_factory` is used to create wrapped loggers that are
    # used for OUTPUT. This one returns a `logging.Logger`. The
    # final value from the final processor (`LogfmtRenderer`) will
    # be passed to the method of the same name as that you've
    # called on the bound logger.
    logger_factory=structlog.stdlib.LoggerFactory(),
    # Effectively freeze configuration after creating the first
    # bound logger.
    cache_logger_on_first_use=True,
)
