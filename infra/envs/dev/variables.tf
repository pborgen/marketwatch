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

variable "monitor_password" {
  type        = string
  description = "Shared password for the agent monitor. Pass TF_VAR_monitor_password. init-market-watch.sh reads MONITOR_PASSWORD from the gitignored .env. GitHub Actions reads the MONITOR_PASSWORD secret."
  sensitive   = true
}

variable "aws_region" {
  type        = string
  description = "Region for resources in this environment. Match the state bucket region in infra/bootstrap."
}
