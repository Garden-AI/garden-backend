resource "aws_ecrpublic_repository" "ecr_repo" {
  repository_name = "garden-containers-${var.env}"
  tags = {
    Component      = "ECR"
    Project        = "Garden"
    RepositoryType = "Public"
  }
}

resource "aws_iam_policy" "ecr_backend_write" {
  name        = "ECRBackendWriteAccess-${var.env}"
  description = "ECR write access for backend application"
  tags        = var.tags

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ecr-public:BatchCheckLayerAvailability",
          "ecr-public:PutImage",
          "ecr-public:InitiateLayerUpload",
          "ecr-public:CompleteLayerUpload",
          "ecr-public:UploadLayerPart",
        ],
        Resource = aws_ecrpublic_repository.ecr_repo.arn,
      },
      {
        Effect = "Allow",
        Action = [
          "ecr-public:GetAuthorizationToken",
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "sts:GetServiceBearerToken",
          "sts:AssumeRole"
        ],
        Resource = "*"
      }
    ]
  })
}
