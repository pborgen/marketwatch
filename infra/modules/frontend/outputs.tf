output "url" {
  description = "HTTPS URL of the hello-world site."
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}
