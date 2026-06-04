variable "name" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "data_sg_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---- Postgres ----------------------------------------------------------------
variable "db_name" {
  type    = string
  default = "petrobrain"
}

variable "db_username" {
  type    = string
  default = "petrobrain"
}

variable "db_engine_version" {
  type    = string
  default = "16.4"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "db_allocated_storage" {
  type    = number
  default = 50
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_deletion_protection" {
  type    = bool
  default = false
}

variable "db_skip_final_snapshot" {
  type    = bool
  default = true
}

# ---- Redis -------------------------------------------------------------------
variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "redis_num_cache_clusters" {
  type    = number
  default = 1
}

variable "redis_automatic_failover" {
  type    = bool
  default = false
}

variable "redis_transit_encryption_enabled" {
  type    = bool
  default = true
}

# ---- S3 ----------------------------------------------------------------------
variable "bucket_name" {
  description = "Globally-unique S3 bucket name for document storage."
  type        = string
}
