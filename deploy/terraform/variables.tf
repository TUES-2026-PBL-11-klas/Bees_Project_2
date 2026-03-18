variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-central-1"
}

variable "eks_role_arn" {
  description = "IAM role for EKS cluster"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for EKS cluster"
  type        = list(string)
}
