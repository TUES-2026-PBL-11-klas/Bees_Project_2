variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, prod)"
  type        = string
  default     = "dev"
}

variable "mongodb_uri" {
  description = "MongoDB Connection URI to store in AWS Secrets Manager"
  type        = string
  sensitive   = true
}
