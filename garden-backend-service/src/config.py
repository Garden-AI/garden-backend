import json
import os
from functools import lru_cache
from typing import Any, Type

import boto3
from dotenv import find_dotenv, load_dotenv
from pydantic import computed_field
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

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

    GARDEN_DEFAULT_SCOPE: str = (
        "https://auth.globus.org/scopes/0948a6b0-a622-4078-b0a4-bfd6d77d65cf/action_all"
    )

    GARDEN_USERS_GROUP_ID: str

    DATACITE_REPO_ID: str
    DATACITE_PASSWORD: str
    DATACITE_ENDPOINT: str
    DATACITE_PREFIX: str

    ECR_REPO_ARN: str
    ECR_ROLE_ARN: str
    STS_TOKEN_TIMEOUT: int = 30 * 60  # 30 min timeout for ecr push

    NOTEBOOKS_S3_BUCKET: str

    GLOBUS_SEARCH_INDEX_ID: str
    SYNC_SEARCH_INDEX: bool
    RETRY_INTERVAL_SECS: int
    MAX_RETRY_COUNT: int

    DB_USERNAME: str
    DB_PASSWORD: str
    DB_ENDPOINT: str

    MDF_API_CLIENT_ID: str
    MDF_API_CLIENT_SECRET: str
    MDF_SEARCH_INDEX_UUID: str

    MODAL_ENABLED: bool
    MODAL_TOKEN_ID: str
    MODAL_TOKEN_SECRET: str
    MODAL_ENV: str = "dev"
    MODAL_USE_LOCAL: bool = False
    MODAL_VIP_LIST: list[str]

    GARDEN_SEARCH_SQL_DIR: str = "src/api/search/sql.sql"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_ENDPOINT}/garden_db_{self.GARDEN_ENV}"

    model_config = SettingsConfigDict(env_file=_dotenv_path, case_sensitive=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        aws_secrets_settings = SecretsmanagerSettingsSource(settings_cls)
        # determines precedence for settings sources
        # i.e. env and dotenv values have priority over settings read from aws;
        # init_settings and file_secret_settings are ignored
        return env_settings, dotenv_settings, aws_secrets_settings


class SecretsmanagerSettingsSource(PydanticBaseSettingsSource):
    """Customise settings to also read configuration variables from an aws secret"""

    def __init__(self, *args, **kwargs):
        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name="us-east-1",
        )
        secret_name = os.getenv("AWS_SECRET_NAME")
        response = client.get_secret_value(SecretId=secret_name)
        self.secrets: dict = json.loads(response["SecretString"])
        super().__init__(*args, **kwargs)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple:
        """Get the value, the key for model creation, and a flag to determine whether value is complex."""
        field_value = self.secrets.get(field_name)
        # False means don't try to parse values as json
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        # see: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
        settings_dict = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_name, _is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, _is_complex
            )
            if field_value is not None:
                settings_dict[field_name] = field_value

        return settings_dict


# for use as dependency with `Depends(get_settings)`
@lru_cache()
def get_settings() -> Settings:
    return Settings()
