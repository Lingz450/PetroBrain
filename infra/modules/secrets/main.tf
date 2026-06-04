# Secrets Manager containers for application secrets. Terraform creates the
# secret and seeds a placeholder version; the real value is set out-of-band
# (console / CI / `aws secretsmanager put-secret-value`) and Terraform ignores
# subsequent value changes so rotation does not fight state. See RUNBOOK.md.

variable "name" {
  type = string
}

variable "recovery_window_in_days" {
  description = "0 for dev (immediate delete), 7-30 for prod."
  type        = number
  default     = 7
}

variable "secret_keys" {
  description = "Logical secret names to provision (value set out-of-band)."
  type        = list(string)
  default     = ["jwt-secret", "metrics-auth-token", "anthropic-api-key", "openai-api-key"]
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_secretsmanager_secret" "app" {
  for_each                = toset(var.secret_keys)
  name                    = "${var.name}/${each.key}"
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "random_password" "metrics_auth_token" {
  length  = 48
  special = false
}

locals {
  generated_secret_values = {
    jwt-secret         = random_password.jwt_secret.result
    metrics-auth-token = random_password.metrics_auth_token.result
  }
}

resource "aws_secretsmanager_secret_version" "app" {
  for_each      = aws_secretsmanager_secret.app
  secret_id     = each.value.id
  secret_string = lookup(local.generated_secret_values, each.key, "REPLACE_ME_VIA_RUNBOOK")
  lifecycle {
    ignore_changes = [secret_string]
  }
}

output "secret_arns" {
  description = "Map of logical secret name -> ARN, for ECS secret injection."
  value       = { for k, s in aws_secretsmanager_secret.app : k => s.arn }
}
