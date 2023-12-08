import boto3
import json

ECR_REPO_ARN_PROD = 'arn:aws:ecr-public::128137667265:repository/garden-containers-prod'
ECR_REPO_ARN_DEV = 'arn:aws:ecr-public::128137667265:repository/garden-containers-dev'
ECR_ROLE_ARN_PROD = 'arn:aws:iam::557062710055:policy/ECRBackendWriteAccess-prod'
ECR_ROLE_ARN_DEV = 'arn:aws:iam::557062710055:policy/ECRBackendWriteAccess-dev'

STS_TOKEN_TIMEOUT = 3 * 60 * 60 # 3 hour timeout

def create_ecr_sts_token(event, _context, _kwargs):
	ECR_REPO_ARN = ECR_REPO_ARN_PROD if get_environment_from_arn() == "prod" else ECR_REPO_ARN_DEV
	ECR_ROLE_ARN = ECR_ROLE_ARN_PROD if get_environment_from_arn() == "prod" else ECR_ROLE_ARN_DEV

    try:
	    sts_client = boto3.client('sts')

	    # Assume a role to get temporary credentials
	    assumed_role = sts_client.assume_role(
	        RoleArn=ECR_ROLE_ARN,
	        RoleSessionName="ECR_TOKEN_ROLE",
	        DurationSeconds=STS_TOKEN_TIMEOUT,
	        Policy=json.dumps({
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
                            "ecr-public:GetAuthorizationToken", #so user can get auth token for docker login
                            "sts:GetServiceBearerToken" #needed for ecr-public:GetAuthorizationToken
                        ],
                        "Resource": ECR_REPO_ARN
                    }
                ]
            })
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
	except Exception as e:
		return {
	        'statusCode': 400,
	        "body": str(e)
	    }

"""
#CLI Push Code
def push_image(sts_creds, repository_uri, new_image_tag, original_image_id, region_name):
    docker_client = docker.from_env()

	# tag the image to push
    image = docker_client.images.get(original_image_id)
    image.tag(f"{repository_uri}/{new_image_name}", tag=new_image_tag)

	# get docker login password from sts token
    session = boto3.session.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=region
    )
    ecr_client = session.client('ecr-public')
    response = ecr_client.get_authorization_token()
    auth_data = response['authorizationData']
    if isinstance(auth_data, list):
        auth_data = auth_data[0]
    password = base64.b64decode(auth_data['authorizationToken']).decode().split(':')[1]
    auth_config = {'username': 'AWS', 'password': password}

    response = docker_client.images.push(f"{repository_uri}:{new_image_tag}", auth_config=auth_config, stream=True, decode=True)
    for line in response:
        print(line)


if __name__ == "__main__":
    REGION_NAME = 'us-east-1'
    REPOSITORY_URI = 'public.ecr.aws/o2h2o7o8/max-garden-test'
    NEW_IMAGE_TAG = 'image-test'
    ORIGINAL_IMAGE_ID = '2de5be708648'
	STS_CREDS = .....

    push_image(STS_CREDS, REPOSITORY_URI, NEW_IMAGE_TAG, ORIGINAL_IMAGE_ID, REGION_NAME)
"""
