variable "name" {
  type        = string
  description = "Name prefix for the cluster, service, and repository."
}

variable "aws_region" {
  type        = string
  description = "Region for the task, logs, and ECR login."
}

variable "vpc_id" {
  type        = string
  description = "VPC for the load balancer target group."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the load balancer and tasks."
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group for the load balancer."
}

variable "api_security_group_id" {
  type        = string
  description = "Security group for the tasks."
}

variable "image_tag" {
  type        = string
  description = "Image tag. A change rebuilds and redeploys the API."
}

variable "repo_root" {
  type        = string
  description = "Repository root. The image publish script runs from here."
}

variable "environment" {
  type        = map(string)
  description = "Extra container environment variables."
}

variable "data_bucket_arn" {
  type        = string
  description = "Application bucket the API, and later agents, can read and write."
}

variable "secret_arns" {
  type        = list(string)
  description = "Database secrets the task may read."
}

variable "opensearch_domain_arn" {
  type        = string
  description = "OpenSearch domain the task may query."
}

variable "cpu_architecture" {
  type        = string
  description = "Fargate CPU architecture. Must match docker_platform."
  default     = "ARM64"
}

variable "docker_platform" {
  type        = string
  description = "docker build --platform value."
  default     = "linux/arm64"
}
