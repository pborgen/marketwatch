output "dns_name" {
  description = "Load balancer hostname. CloudFront uses this as its origin."
  value       = aws_lb.api.dns_name
}

output "url" {
  description = "HTTP URL of the API load balancer."
  value       = "http://${aws_lb.api.dns_name}"
}

output "repository_url" {
  description = "ECR repository for the API image."
  value       = aws_ecr_repository.api.repository_url
}
