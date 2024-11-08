import json
from typing import Literal

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends

from src.config import Settings, get_settings
from src.exceptions.modal import ModalException
from src.sandboxed_functions.lambda_function import (
    DeployModalAppArgs,
    ValidateModalFileArgs,
    deploy_modal_app,
    validate_modal_file,
)


def make_lambda_invoker(
    function_name: str,
    sub_function_name: Literal["deploy_modal_app", "validate_modal_file"],
) -> callable:
    lambda_client = boto3.client("lambda", "us-east-1")

    def invoke_lambda_fn(fn_args: dict):
        payload = {"fn_name": sub_function_name, "fn_args": fn_args}
        try:
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",  # Synchronous invocation
                Payload=json.dumps(payload),
            )

        except ClientError as e:
            # TODO: when do we hit this error?
            # Replace this with logging
            print(f"Failed to invoke Lambda function: {str(e)}")
            raise

        if response["StatusCode"] not in (200, 201, 202):
            raise Exception(
                f"Lambda invocation failed with status {response['StatusCode']}"
            )

        response_payload = json.loads(response["Payload"].read().decode("utf-8"))

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

        return response_payload

    return invoke_lambda_fn


def make_local_invoker(sub_function: callable) -> callable:
    def invoke_local_fn(fn_args: dict):
        response_payload = sub_function(fn_args)

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
