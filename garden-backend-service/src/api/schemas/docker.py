from pydantic import BaseModel


class ECRPushCredentials(BaseModel):
    AccessKeyId: str
    SecretAccessKey: str
    SessionToken: str
    ECRRepo: str
    RegionName: str = "us-east-1"
