import boto3
import json

ECR_REPO_ARN_PROD = 'arn:aws:ecr-public::128137667265:repository/garden-containers-prod'
ECR_REPO_ARN_DEV = 'arn:aws:ecr-public::128137667265:repository/garden-containers-dev'
ECR_ROLE_ARN_PROD = 'arn:aws:iam::557062710055:policy/ECRBackendWriteAccess-prod'
ECR_ROLE_ARN_DEV = 'arn:aws:iam::557062710055:policy/ECRBackendWriteAccess-dev'

STS_TOKEN_TIMEOUT = 3 * 60 * 60 # 3 hour timeout

def create_ecr_sts_token(event, _context, _kwargs):
    try:
	    sts_client = boto3.client('sts')

	    # Assume a role to get temporary credentials
	    assumed_role = sts_client.assume_role(
	        RoleArn=ECR_ROLE_ARN,
	        RoleSessionName="ECR_TOKEN_ROLE",
	        DurationSeconds=STS_TOKEN_TIMEOUT
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




