terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 1. VPC Module
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.5.0"

  name = "clearwake-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true
}

# 2. EKS Cluster Module
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.5.0"

  cluster_name    = "clearwake-cluster"
  cluster_version = "1.29"

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.public_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    app_nodes = {
      min_size     = 1
      max_size     = 3
      desired_size = 2

      instance_types = ["t3.medium"]
    }
  }
}

# 3. Configuration & Secrets Management (AWS Secrets Manager)
resource "aws_secretsmanager_secret" "mongodb_uri" {
  name        = "clearwake/mongodb-uri"
  description = "MongoDB connection string for the API"
}

resource "aws_secretsmanager_secret_version" "mongodb_uri_val" {
  secret_id     = aws_secretsmanager_secret.mongodb_uri.id
  secret_string = jsonencode({ "MONGODB_URI" = var.mongodb_uri })
}

# 4. S3 Bucket for Route Artifacts/Observability Logs
resource "aws_s3_bucket" "clearwake_data" {
  bucket        = "clearwake-data-${var.environment}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "clearwake_data_block" {
  bucket = aws_s3_bucket.clearwake_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
