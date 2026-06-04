# Data tier: RDS PostgreSQL (pgvector-capable, encrypted, private), ElastiCache
# Redis (encrypted at rest, private), and the in-region S3 document bucket.
# Everything lives in private subnets reachable only from the app SG. The
# assembled DATABASE_URL is stored in Secrets Manager for ECS to inject.

# ---- Postgres ----------------------------------------------------------------

resource "random_password" "db" {
  length  = 32
  special = false # alphanumeric keeps the connection URL unambiguous
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-db"
  subnet_ids = var.private_subnet_ids
  tags       = merge(var.tags, { Name = "${var.name}-db-subnets" })
}

resource "aws_db_parameter_group" "this" {
  name        = "${var.name}-pg16"
  family      = "postgres16"
  description = "PetroBrain Postgres params: enforce TLS."
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  tags = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name}-pg"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 4
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.data_sg_id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false

  multi_az                   = var.db_multi_az
  backup_retention_period    = var.db_backup_retention_days
  auto_minor_version_upgrade = true
  deletion_protection        = var.db_deletion_protection
  skip_final_snapshot        = var.db_skip_final_snapshot
  final_snapshot_identifier  = var.db_skip_final_snapshot ? null : "${var.name}-pg-final"

  tags = merge(var.tags, { Name = "${var.name}-pg" })
}

# DATABASE_URL secret (asyncpg-style; app's pg.normalize_dsn strips the suffix).
resource "aws_secretsmanager_secret" "db_url" {
  name                    = "${var.name}/database-url"
  recovery_window_in_days = 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "db_url" {
  secret_id = aws_secretsmanager_secret.db_url.id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:%d/%s",
    var.db_username,
    random_password.db.result,
    aws_db_instance.this.address,
    aws_db_instance.this.port,
    var.db_name,
  )
}

# ---- Redis -------------------------------------------------------------------

resource "random_password" "redis_auth" {
  length  = 48
  special = false
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name}-redis"
  description          = "PetroBrain Redis (broker + cache)."
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  port                 = 6379

  num_cache_clusters         = var.redis_num_cache_clusters
  automatic_failover_enabled = var.redis_automatic_failover
  multi_az_enabled           = var.redis_automatic_failover

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [var.data_sg_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = var.redis_transit_encryption_enabled
  auth_token                 = var.redis_transit_encryption_enabled ? random_password.redis_auth.result : null

  tags = merge(var.tags, { Name = "${var.name}-redis" })
}

locals {
  redis_scheme          = var.redis_transit_encryption_enabled ? "rediss" : "redis"
  redis_authority       = var.redis_transit_encryption_enabled ? format(":%s@", random_password.redis_auth.result) : ""
  redis_primary_address = aws_elasticache_replication_group.this.primary_endpoint_address
  redis_base_url        = format("%s://%s%s:%d", local.redis_scheme, local.redis_authority, local.redis_primary_address, 6379)
}

resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "${var.name}/redis-url"
  recovery_window_in_days = 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id     = aws_secretsmanager_secret.redis_url.id
  secret_string = "${local.redis_base_url}/0"
}

resource "aws_secretsmanager_secret" "celery_broker_url" {
  name                    = "${var.name}/celery-broker-url"
  recovery_window_in_days = 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "celery_broker_url" {
  secret_id     = aws_secretsmanager_secret.celery_broker_url.id
  secret_string = "${local.redis_base_url}/1"
}

resource "aws_secretsmanager_secret" "celery_result_backend" {
  name                    = "${var.name}/celery-result-backend"
  recovery_window_in_days = 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "celery_result_backend" {
  secret_id     = aws_secretsmanager_secret.celery_result_backend.id
  secret_string = "${local.redis_base_url}/2"
}

# ---- S3 ----------------------------------------------------------------------

resource "aws_s3_bucket" "docs" {
  bucket = var.bucket_name
  tags   = merge(var.tags, { Name = var.bucket_name })
}

resource "aws_s3_bucket_versioning" "docs" {
  bucket = aws_s3_bucket.docs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
