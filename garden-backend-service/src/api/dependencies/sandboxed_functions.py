import json
from typing import Literal

import boto3
from fastapi import Depends

from src.config import Settings, get_settings
from src.exceptions.modal import ModalException
from src.sandboxed_functions.lambda_function import (
    DeployModalAppArgs,
    ValidateModalFileArgs,
    deploy_modal_app,
    validate_modal_file,
)

# This module handles boilerplate for turning our sandboxed code execution functions into FastAPI dependencies.
# We want to inject the functions into our route handlers as dependencies,
# so that we can swap out whether we run them locally or remotely.
# (In practice, you will only use the local version when developing locally.)
# Making functions into FastAPI dependencies is awkward,
# and we need to use this pattern of callable classes to make it work.
#
# The exposed callables take a dictionary (shaped like ValidateModalFileArgs or DeployModalAppArgs)
# and return a dictionary with the response payload.
# Because the functions are designed to run remotely, they will swallow exceptions and return them as strings in a dict.
# The wrappers in this file handle dectect the error messages and raise them as exceptions.
# So a caller invoking the functions does not need to inspect the dict for error messages.


def _raise_exception_if_error_in_lambda_response(response_payload: dict):
    if "ModalException" in response_payload:
        details = response_payload["ModalException"]
        raise ModalException(
            detail=details["detail"],
            suggested_fix=details["suggested_fix"],
            status_code=details["status_code"],
        )
    elif "Exception" in response_payload:
        details = response_payload["Exception"]
        raise Exception(
            detail=details["detail"],
        )


def make_lambda_invoker(
    function_name: str,
    sub_function_name: Literal["deploy_modal_app", "validate_modal_file"],
) -> callable:
    lambda_client = boto3.client("lambda", "us-east-1")

    def invoke_lambda_fn(fn_args: dict):
        payload = {"fn_name": sub_function_name, "fn_args": fn_args}

        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",  # Synchronous invocation
            Payload=json.dumps(payload),
        )

        if response["StatusCode"] not in (200, 201, 202):
            raise Exception(
                f"Lambda invocation failed with status {response['StatusCode']}"
            )

        response_payload = json.loads(response["Payload"].read().decode("utf-8"))
        _raise_exception_if_error_in_lambda_response(response_payload)
        return response_payload

    return invoke_lambda_fn


def make_local_invoker(sub_function: callable) -> callable:
    def invoke_local_fn(fn_args: dict):
        response_payload = sub_function(fn_args)
        _raise_exception_if_error_in_lambda_response(response_payload)
        return response_payload

    return invoke_local_fn


class ValidateModalFileProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        if settings.MODAL_USE_LOCAL:
            self.f = make_local_invoker(validate_modal_file)
        else:
            lambda_function_name = f"GardenSandbox-{settings.GARDEN_ENV}"
            self.f = make_lambda_invoker(lambda_function_name, "validate_modal_file")

    def __call__(self, fn_args: ValidateModalFileArgs):
        return self.f(fn_args)


class DeployModalAppProvider:
    def __init__(self, settings: Settings = Depends(get_settings)):
        if settings.MODAL_USE_LOCAL:
            self.f = make_local_invoker(deploy_modal_app)
        else:
            lambda_function_name = f"GardenSandbox-{settings.GARDEN_ENV}"
            self.f = make_lambda_invoker(lambda_function_name, "deploy_modal_app")

    def __call__(
        self,
        fn_args: DeployModalAppArgs,
    ):
        return self.f(fn_args)
