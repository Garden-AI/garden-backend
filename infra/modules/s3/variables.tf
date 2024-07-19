variable "tags" {
  type = map(string)
  default = {
    Project = "Garden"
  }
}

variable "env" {
  description = "The environment for the deployment. (dev, prod)"
  type        = string
}
