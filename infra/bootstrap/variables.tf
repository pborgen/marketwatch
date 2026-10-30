variable "project" {
  type        = string
  description = "Short project name. Used as the state bucket prefix."

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$", var.project))
    error_message = "project must be 3-40 characters: lowercase letters, digits, and hyphens."
  }
}

variable "aws_region" {
  type        = string
  description = "Region for the state bucket. Use the same value in infra/envs/*/terraform.tfvars."
}
