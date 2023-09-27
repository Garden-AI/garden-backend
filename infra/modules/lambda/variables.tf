variable "env" {
  description = "The environment for the deployment. (dev, prod)"
  type        = string
}

variable "s3_access_policy_arn" {
  description = "The ARN for the S3 access policy to attach to the lambda_exec role."
  type        = string
}

variable "api_gateway_execution_arn" {
  description = "The execution ARN for the API Gateway."
  type        = string
}
