This container has been built one-off from a Garden dev's machine and pushed to a public AWS ECR repo.

Below are the commands to tweak and run to publish a new version.

```
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/x2v7f8j4
docker build . --platform linux/amd64 -t public.ecr.aws/x2v7f8j4/mlflow:[version]
docker push public.ecr.aws/x2v7f8j4/mlflow:[version]
```