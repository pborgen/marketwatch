variable "name" {
  type        = string
  description = "Domain name. 3-28 characters: lowercase letters, digits, and hyphens."
}

variable "aws_region" {
  type        = string
  description = "Region for the domain ARN in the access policy."
}

variable "subnet_id" {
  type        = string
  description = "One private subnet. A single-node domain uses one subnet."
}

variable "security_group_id" {
  type        = string
  description = "Security group that allows HTTPS from the API."
}
