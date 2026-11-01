output "endpoint" {
  description = "HTTPS endpoint of the OpenSearch domain."
  value       = "https://${aws_opensearch_domain.this.endpoint}"
}

output "domain_arn" {
  description = "ARN of the OpenSearch domain."
  value       = aws_opensearch_domain.this.arn
}
