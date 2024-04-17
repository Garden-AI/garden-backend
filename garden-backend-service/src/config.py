import json
import os
from functools import lru_cache
from typing import Any

import boto3
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseSettings

# read from .env if it exists (local development only)
_dotenv_path = find_dotenv()
load_dotenv(str(_dotenv_path), override=False)


class Settings(BaseSettings):
    DEBUG: bool = False
    LOGLEVEL: str = "INFO"

    # set by deployment
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_SECRET_NAME: str
    GARDEN_ENV: str

    # for globus auth confidential client
    API_CLIENT_ID: str
    API_CLIENT_SECRET: str

    GARDEN_DEFAULT_SCOPE = (
        "https://auth.globus.org/scopes/0948a6b0-a622-4078-b0a4-bfd6d77d65cf/action_all"
    )

    DATACITE_REPO_ID: str
    DATACITE_PASSWORD: str
    DATACITE_ENDPOINT: str
    DATACITE_PREFIX: str

    class Config:
        case_sensitive = True
        env_file = _dotenv_path

        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ):
            # populate values from secretsmanager helper as well as env variables
            return (
                init_settings,
                env_settings,
                file_secret_settings,
                _aws_secretsmanager_settings_source,  # see below
            )


def _aws_secretsmanager_settings_source(settings: BaseSettings) -> dict[str, Any]:
    """Helper: read json from AWS secretsmanager to populate Settings object.

    Requires aws credentials to have been set by appropriate env vars.
    """
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name="us-east-1",
    )
    secret_name = os.getenv("AWS_SECRET_NAME")
    response = client.get_secret_value(SecretId=secret_name)
    secrets: dict = json.loads(response["SecretString"])
    return secrets


# for use as dependency with `Depends(get_settings)`
@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
