resource "aws_s3_bucket" "pipeline_notebooks_bucket" {
  bucket = "pipeline-notebooks-${var.env}"
  tags   = var.tags
}

# Allow anyone to read the contents of the bucket
resource "aws_s3_bucket_policy" "public_read_policy" {
  bucket = aws_s3_bucket.pipeline_notebooks_bucket.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = "*",
        Action    = "s3:GetObject",
        Resource  = "${aws_s3_bucket.pipeline_notebooks_bucket.arn}/*"
      }
    ]
  })
}

# But only the backend can write to it
resource "aws_iam_policy" "s3_full_access" {
  name        = "s3_full_access-${var.env}"
  description = "Full access to notebook bucket"
  tags        = var.tags

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

# Let browsers access files in the bucket
resource "aws_s3_bucket_cors_configuration" "pipeline_notebooks_cors" {
  bucket = aws_s3_bucket.pipeline_notebooks_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = []
    max_age_seconds = 3000
  }
}
