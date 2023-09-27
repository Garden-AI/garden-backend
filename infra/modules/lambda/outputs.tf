output "garden_app_invoke_arn" {
  value = aws_lambda_function.garden_app.invoke_arn
}

output "garden_app_function_name" {
  value = aws_lambda_function.garden_app.function_name
}

output "garden_authorizer_invoke_arn" {
  value = aws_lambda_function.garden_authorizer.invoke_arn
}

output "garden_authorizer_function_name" {
  value = aws_lambda_function.garden_authorizer.function_name
}


output "lambda_exec_role_name" {
  value = aws_iam_role.lambda_exec.name
}
