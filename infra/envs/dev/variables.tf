variable "region" {
  type    = string
  default = "af-south-1"
}

variable "image" {
  description = "Container image URI for API + worker (ECR)."
  type        = string
}

variable "bucket_name" {
  description = "Globally-unique S3 document bucket name."
  type        = string
}

variable "certificate_arn" {
  description = "ACM cert ARN for HTTPS. Empty = HTTP-only (dev only)."
  type        = string
  default     = ""
}

variable "cors_allow_origins" {
  description = "Comma-separated dev browser origins allowed to call the API."
  type        = string
  default     = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
}
