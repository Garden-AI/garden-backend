output "garden_sandbox_fn_invoke_arn" {
  value = aws_lambda_function.sandboxed_app.invoke_arn
}

output "garden_sandbox_fn_function_name" {
  value = aws_lambda_function.sandboxed_app.function_name
}

output "lambda_exec_role_name" {
  value = aws_iam_role.lambda_exec.name
}
