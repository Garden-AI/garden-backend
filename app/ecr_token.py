import boto3
import json

from utils import get_environment_from_arn

ECR_REPO_ARN_PROD = 'arn:aws:ecr-public::128137667265:repository/garden-containers-prod'
ECR_REPO_ARN_DEV = 'arn:aws:ecr-public::128137667265:repository/garden-containers-dev'
ECR_ROLE_ARN_PROD = 'arn:aws:iam::557062710055:role/ecr_puller_prod'
ECR_ROLE_ARN_DEV = 'arn:aws:iam::557062710055:role/ecr_puller_dev'

STS_TOKEN_TIMEOUT = 60 * 30 # 30 minute timeout

def create_ecr_sts_token(event, _context, _kwargs):
    running_in_prod = get_environment_from_arn() == "prod"
    ECR_REPO_ARN = ECR_REPO_ARN_PROD if running_in_prod else ECR_REPO_ARN_DEV
    ECR_ROLE_ARN = ECR_ROLE_ARN_PROD if running_in_prod else ECR_ROLE_ARN_DEV

    sts_client = boto3.client('sts')

    user_policy = json.dumps({
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
                "Resource": ECR_REPO_ARN
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ecr-public:GetAuthorizationToken",  # so user can get auth token for docker login
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sts:GetServiceBearerToken",  # needed for ecr-public:GetAuthorizationToken
                    "sts:AssumeRole"
                ],
                "Resource": "*"
            }
        ]
    })

    # Assume a role to get temporary credentials
    assumed_role = sts_client.assume_role(
        RoleArn=ECR_ROLE_ARN,
        RoleSessionName="ECR_TOKEN_ROLE",
        DurationSeconds=STS_TOKEN_TIMEOUT,
        Policy=user_policy
    )

    # Return the credentials and ECR repo info to the user
    credentials = assumed_role['Credentials']
    return {
        'statusCode': 200,
        'body': json.dumps({
            'AccessKeyId': credentials['AccessKeyId'],
            'SecretAccessKey': credentials['SecretAccessKey'],
            'SessionToken': credentials['SessionToken'],
            'ECRRepo': ECR_REPO_ARN
        })
    }
