resource "aws_s3_bucket" "prod_models" {
  bucket = "garden-mlflow-models-prod"
  tags   = var.tags
}

resource "aws_s3_bucket" "dev_models" {
  bucket = "garden-mlflow-models-dev"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "prod" {
  bucket = aws_s3_bucket.prod_models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "dev" {
  bucket = aws_s3_bucket.dev_models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_policy" "s3_full_access" {
  name        = "s3_full_access"
  description = "Full access to prod and dev MLFlow model buckets"

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : "s3:*",
        "Resource" : [
          "${aws_s3_bucket.prod_models.arn}/*",
          aws_s3_bucket.prod_models.arn,
          "${aws_s3_bucket.dev_models.arn}/*",
          aws_s3_bucket.dev_models.arn
        ]
      }
    ]
  })
}