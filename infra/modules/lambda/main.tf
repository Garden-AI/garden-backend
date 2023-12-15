/* Authorizer Lambda */

resource "aws_lambda_function" "garden_authorizer" {
  function_name = "GardenAuthorizer-${var.env}"

  filename = "authorizer.zip"
  runtime  = "python3.9"
  handler  = "lambda_function.lambda_handler"

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_cloudwatch_log_group" "garden_authorizer" {
  name = "/aws/lambda/${aws_lambda_function.garden_authorizer.function_name}"

  retention_in_days = 30
}

/* App Lambda */

resource "aws_lambda_function" "garden_app" {
  function_name = "GardenApp-${var.env}"

  filename = "app.zip"
  runtime  = "python3.9"
  handler  = "lambda_function.lambda_handler"

  role    = aws_iam_role.lambda_exec.arn
  timeout = 10
}

resource "aws_cloudwatch_log_group" "garden_app" {
  name = "/aws/lambda/${aws_lambda_function.garden_app.function_name}"

  retention_in_days = 30
}

/* Connect the auth/app Lambdas to the gateway */

resource "aws_lambda_permission" "garden_api_auth_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_authorizer.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${var.api_gateway_execution_arn}/*/*"
}

resource "aws_lambda_permission" "garden_api_app_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_app.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${var.api_gateway_execution_arn}/*/*"
}

/* IAM resources */

resource "aws_iam_role" "lambda_exec" {
  name = "garden_lambda_${var.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role" "assumable_role" {
  name = "ecr_puller_${var.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          AWS = aws_iam_role.lambda_exec.arn
        },
      },
    ],
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "s3_access_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = var.s3_access_policy_arn
}

  resource "aws_iam_role_policy_attachment" "ecr_access_attach" {
    role       = aws_iam_role.assumable_role.name
    policy_arn = var.ecr_access_policy_arn
  }
