provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "clearwake_bucket" {
  bucket = "clearwake-data"
  acl    = "private"
}

resource "aws_eks_cluster" "clearwake_cluster" {
  name     = "clearwake-cluster"
  role_arn = var.eks_role_arn
  version  = "1.25"

  vpc_config {
    subnet_ids = var.subnet_ids
  }
}
