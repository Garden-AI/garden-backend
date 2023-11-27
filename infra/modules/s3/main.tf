resource "aws_s3_bucket" "pipeline_notebooks_bucket" {
  bucket = "pipeline-notebooks-${var.env}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "pipeline_notebooks_access_block" {
  bucket = aws_s3_bucket.pipeline_notebooks_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_policy" "s3_full_access" {
  name        = "s3_full_access"
  description = "Full access to notebook bucket"

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : "s3:*",
        "Resource" : [
          "${aws_s3_bucket.pipeline_notebooks_bucket.arn}/*",
          aws_s3_bucket.pipeline_notebooks_bucket.arn,
        ]
      }
    ]
  })
}
