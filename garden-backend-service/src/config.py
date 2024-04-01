from functools import lru_cache

from pydantic import BaseSettings
from dotenv import find_dotenv


class Settings(BaseSettings):
    DEBUG: bool = False
    LOGLEVEL: str = "INFO"
    API_CLIENT_ID: str = "API_CLIENT_ID"
    API_CLIENT_SECRET: str = "API_CLIENT_SECRET"

    # TODO change to action_all?
    GARDEN_DEFAULT_SCOPE = (
        "https://auth.globus.org/scopes/0948a6b0-a622-4078-b0a4-bfd6d77d65cf/test_scope"
    )

    class Config:
        case_sensitive = True
        env_file = find_dotenv()


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
