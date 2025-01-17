/* Sandboxed Lambda */

resource "aws_lambda_function" "sandboxed_app" {
  function_name = "GardenSandbox-${var.env}"

  filename = "app.zip"
  runtime  = "python3.12"
  handler  = "lambda_function.lambda_handler"

  role    = aws_iam_role.lambda_exec.arn
  # Starting with 5 minutes.
  timeout = 300
  # Lambda allocates vCPUs proportional to the memory size,
  # and this memory size is equivalent to one vCPU.
  memory_size = 1769
}

resource "aws_cloudwatch_log_group" "sandboxed_app" {
  name = "/aws/lambda/${aws_lambda_function.sandboxed_app.function_name}"

  retention_in_days = 30
}

/* Connect the sandboxed Lambdas to the FastAPI App */

resource "aws_lambda_permission" "garden_lambda_from_server_permission" {
  statement_id  = "AllowExecutionFromLightsail"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sandboxed_app.function_name
  principal     = "lightsail.amazonaws.com"

  # Allow invocation from the specific Lightsail container service
  source_arn = "arn:aws:lightsail:us-east-1:${var.aws_account_id}:container-service/${var.server_name}"
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

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
