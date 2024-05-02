import json

import boto3
from fastapi import APIRouter, Depends, status
from src.config import Settings, get_settings

from src.api.dependencies.auth import AuthenticationState, authenticated
from src.api.schemas.docker import ECRPushCredentials

router = APIRouter(prefix="/docker-push-token")


@router.get("", status_code=status.HTTP_200_OK)
async def get_push_session(
    settings: Settings = Depends(get_settings),
    _auth: AuthenticationState = Depends(authenticated),
) -> ECRPushCredentials:
    sts_client = boto3.client("sts")
    user_policy = _build_user_policy(settings.ECR_REPO_ARN)

    # Assume a role to get temporary credentials
    assumed_role = sts_client.assume_role(
        RoleArn=settings.ECR_ROLE_ARN,
        RoleSessionName="ECR_TOKEN_ROLE",
        DurationSeconds=settings.STS_TOKEN_TIMEOUT,
        Policy=user_policy,
    )

    credentials = assumed_role["Credentials"]
    return ECRPushCredentials(**credentials, ECRRepo=settings.ECR_REPO_ARN)


def _build_user_policy(ecr_repo_arn: str) -> str:
    user_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr-public:GetDownloadUrlForLayer",
                        "ecr-public:BatchGetImage",
                        "ecr-public:BatchCheckLayerAvailability",
                        "ecr-public:PutImage",
                        "ecr-public:InitiateLayerUpload",
                        "ecr-public:UploadLayerPart",
                        "ecr-public:CompleteLayerUpload",
                    ],
                    "Resource": ecr_repo_arn,
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr-public:GetAuthorizationToken",  # so user can get auth token for docker login
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "sts:GetServiceBearerToken",  # needed for ecr-public:GetAuthorizationToken
                        "sts:AssumeRole",
                    ],
                    "Resource": "*",
                },
            ],
        }
    )
    return user_policy
