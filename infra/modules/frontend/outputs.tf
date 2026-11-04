output "url" {
  description = "HTTPS URL of the agent monitor."
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}
