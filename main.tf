# Data source for Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  project_name        = local.project_name
  vpc_cidr            = "10.0.0.0/16"
  public_subnet_cidr  = "10.0.1.0/24"
  private_subnet_cidr = "10.0.2.0/24"
}

# Security Group
resource "aws_security_group" "ec2_sg" {
  name        = "${local.project_name}-sg"
  description = "Security group for EC2 workers (SSM access via Session Manager)"
  vpc_id      = module.vpc.vpc_id

  # SSM Session Manager uses HTTPS outbound to AWS endpoints (already allowed by egress)
  # No ingress rules needed - SSM doesn't require open ports

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.project_name}-sg"
  }
}

# S3 Bucket
resource "aws_s3_bucket" "demo" {
  bucket = local.bucket_name

  force_destroy = true

  tags = {
    Name = local.bucket_name
  }
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Upload scripts to S3
resource "aws_s3_object" "scripts" {
  for_each = local.scripts

  bucket = aws_s3_bucket.demo.id
  key    = each.value
  source = "${path.module}/${each.value}"
  etag   = filemd5("${path.module}/${each.value}")
}

# IAM Role for EC2 instances
resource "aws_iam_role" "ec2_role" {
  name = "${local.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Attach AWS managed policy for SSM
resource "aws_iam_role_policy_attachment" "ssm_managed_instance_core" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# IAM Policy for S3 access and EC2 tag reading
resource "aws_iam_role_policy" "ec2_s3_policy" {
  name = "${local.project_name}-s3-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ReadAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          "${aws_s3_bucket.demo.arn}/*"
        ]
      },
      {
        Sid    = "S3ListBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.demo.arn}"
        ]
      },
      {
        Sid    = "S3WriteAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:CreateMultipartUpload",
          "s3:CompleteMultipartUpload",
          "s3:AbortMultipartUpload",
          "s3:UploadPart"
        ]
        Resource = [
          "${aws_s3_bucket.demo.arn}/*"
        ]
      },
      {
        Sid    = "EC2DescribeTags"
        Effect = "Allow"
        Action = [
          "ec2:DescribeTags"
        ]
        Resource = "*"
      }
    ]
  })
}

# Instance Profile
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${local.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# User data template
locals {
  user_data = templatefile("${path.module}/templates/user_data.sh.tftpl", {
    bucket_name       = aws_s3_bucket.demo.id
    target_object_key = var.target_s3_object_key
    worker_count      = var.worker_count
    chunk_size_mb     = var.chunk_size_mb
    region            = var.region
  })
}

# EC2 Instances
resource "aws_instance" "workers" {
  count                       = var.worker_count
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = module.vpc.private_subnet_id
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids      = [aws_security_group.ec2_sg.id]

  user_data                   = local.user_data
  user_data_replace_on_change = true

  tags = {
    Name     = "${local.project_name}-worker-${count.index}"
    WorkerID = count.index
    Project  = local.project_name
  }

  lifecycle {
    create_before_destroy = true
  }
}
