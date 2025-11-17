variable "worker_count" {
  description = "Number of EC2 worker instances"
  type        = number
  default     = 3
}

variable "instance_type" {
  description = "EC2 instance type for workers (minimum: t3.micro)"
  type        = string
  default     = "t3.small"
}

variable "bucket_name" {
  description = "S3 bucket name (leave empty to auto-generate)"
  type        = string
  default     = ""
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-2"
}

variable "target_s3_object_key" {
  description = "S3 object key to download every minute"
  type        = string
  default     = "demo/large-file.bin"
}

variable "chunk_size_mb" {
  description = "Size of each byte range chunk in MB"
  type        = number
  default     = 100
}
