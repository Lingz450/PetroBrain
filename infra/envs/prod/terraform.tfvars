region = "af-south-1"

# Replace with your ECR image URI, a globally-unique bucket name, and the
# ACM certificate ARN for the API hostname (HTTPS is required in prod).
image              = "ACCOUNT_ID.dkr.ecr.af-south-1.amazonaws.com/petrobrain:prod"
bucket_name        = "petrobrain-docs-prod-CHANGE-ME"
certificate_arn    = "arn:aws:acm:af-south-1:ACCOUNT_ID:certificate/CHANGE-ME"
cors_allow_origins = "https://petrobrain.vercel.app"
