variable "project" {
  type        = string
  description = "Project name applied to default tags. Keep this aligned with infra/bootstrap."
  default     = "marketwatch"
}

variable "environment" {
  type        = string
  description = "Deployment environment name."

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "aws_region" {
  type        = string
  description = "Region for resources in this environment. Match the state bucket region in infra/bootstrap."
}
