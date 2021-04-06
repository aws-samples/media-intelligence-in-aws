version = 0.1
[y]
[y.deploy]
[y.deploy.parameters]
stack_name = "backend"
s3_bucket = "aws-sam-cli-managed-default-samclisourcebucket-qwmxecpzgogx"
s3_prefix = "backend"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Email=\"youremail@yourprovider.com\" S3Bucket=\"globo-dev\" MediaConvertDestinationBucket=\"globo-dev\""
