from pydantic import BaseModel
from src.config import get_settings

settings = get_settings()


class ECRPushCredentials(BaseModel):
    AccessKeyId: str
    SecretAccessKey: str
    SessionToken: str
    ECRRepo: str = settings.ECR_REPO_ARN
    RegionName: str = "us-east-1"
