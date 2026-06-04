provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "PetroBrain"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

module "stack" {
  source = "../../modules/stack"

  env                = "dev"
  region             = var.region
  image              = var.image
  bucket_name        = var.bucket_name
  certificate_arn    = var.certificate_arn
  cors_allow_origins = var.cors_allow_origins

  # Dev posture: cheap, single-AZ, fast teardown.
  single_nat_gateway               = true
  az_count                         = 2
  db_instance_class                = "db.t4g.medium"
  db_allocated_storage             = 20
  db_multi_az                      = false
  db_backup_retention_days         = 1
  db_deletion_protection           = false
  db_skip_final_snapshot           = true
  secret_recovery_window           = 0
  log_retention_days               = 14
  redis_node_type                  = "cache.t4g.micro"
  redis_num_cache_clusters         = 1
  redis_automatic_failover         = false
  redis_transit_encryption_enabled = true
  api_desired_count                = 1
  worker_desired_count             = 1
}
