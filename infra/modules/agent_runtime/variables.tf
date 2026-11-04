variable "name" {
  type        = string
  description = "Name prefix for the repository and execution role."
}

variable "runtime_name" {
  type        = string
  description = "AgentCore runtime name. A letter, then letters, numbers, or underscores."

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,47}$", var.runtime_name))
    error_message = "runtime_name must start with a letter and contain only letters, numbers, and underscores (48 characters max)."
  }
}

variable "aws_region" {
  type        = string
  description = "Region for the runtime, logs, and ECR login."
}

variable "image_tag" {
  type        = string
  description = "Image tag. A change rebuilds and redeploys the agent."
}

variable "repo_root" {
  type        = string
  description = "Repository root. The image publish script runs from here."
}

variable "model_id" {
  type        = string
  description = "Bedrock model id passed to the container as STRANDS_MODEL_ID."
}

variable "dockerfile" {
  type        = string
  description = "Dockerfile path relative to repo_root."
  default     = "apps/agents/demo/Dockerfile"
}

variable "description" {
  type        = string
  description = "Runtime description shown in AgentCore."
  default     = "Market-watch demo agent."
}

variable "data_bucket_arn" {
  type        = string
  description = "Bucket the runtime may read and write. Empty skips the S3 policy."
  default     = ""
}

variable "data_bucket_name" {
  type        = string
  description = "DATA_BUCKET value in the runtime. Empty leaves the variable unset."
  default     = ""
}
