# Get availability zones (excluding local zones)
data "aws_availability_zones" "available" {
  state                  = "available"
  all_availability_zones = false

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required", "opted-in"]
  }

  # Exclude local zones
  filter {
    name   = "zone-type"
    values = ["availability-zone"]
  }
}

# VPC
resource "aws_vpc" "demo" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# Public Subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = var.availability_zone != "" ? var.availability_zone : data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

# Private Subnet
resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = var.private_subnet_cidr
  availability_zone       = var.availability_zone != "" ? var.availability_zone : data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.project_name}-private-subnet"
  }
}

# Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

# Route Table Association
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

# NAT Gateway
resource "aws_nat_gateway" "demo" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  depends_on = [aws_internet_gateway.demo]

  tags = {
    Name = "${var.project_name}-nat-gateway"
  }
}

# Private Route Table
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.demo.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.demo.id
  }

  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

# Private Route Table Association
resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
