# The monitor is the API. CloudFront is the HTTPS front door. The API
# refuses every page except /health until the shared demo password is sent.

resource "aws_cloudfront_distribution" "web" {
  enabled      = true
  comment      = var.name
  price_class  = "PriceClass_100"
  http_version = "http2"

  origin {
    domain_name = var.origin_domain_name
    origin_id   = "monitor"

    custom_header {
      name  = "X-Monitor-Proto"
      value = "https"
    }

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      # Agent commands can take most of a minute.
      origin_read_timeout = 60
    }
  }

  default_cache_behavior {
    target_origin_id       = "monitor"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    # Managed CachingDisabled. Login and commands must not be cached.
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    # Managed AllViewerExceptHostHeader. Forwards the session cookie to the API.
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
