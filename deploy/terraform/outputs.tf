output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.clearwake_cluster.endpoint
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.clearwake_bucket.bucket
}
