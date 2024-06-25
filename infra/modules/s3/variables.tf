variable "tags" {
  type    = map(string)
  default = {}
}

variable "env" {
  description = "The environment for the deployment. (dev, prod)"
  type        = string
}
