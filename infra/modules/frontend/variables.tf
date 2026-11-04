variable "name" {
  type        = string
  description = "Comment recorded on the CloudFront distribution."
}

variable "origin_domain_name" {
  type        = string
  description = "API load balancer hostname. CloudFront connects to it over HTTP."
}
