
resource "aws_ecrpublic_repository" "ecr_repo" {
  repository_name = "garden-containers-${var.env}"
}

resource "aws_iam_policy" "ecr_backend_write" {
  name        = "ECRBackendWriteAccess-${var.env}"
  description = "ECR write access for backend application"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Action    = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ],
        Resource = aws_ecrpublic_repository.ecr_repo.arn,
      }
    ]
  })
}
