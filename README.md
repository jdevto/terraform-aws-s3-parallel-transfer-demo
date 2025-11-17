# S3 High-Throughput Upload and Download Demo

This demo demonstrates how multipart uploads and parallel byte-range downloads can significantly improve performance for large (GB-sized) objects in Amazon S3.

## Overview

### Use Cases

| Phase | Purpose | Technique |
|-------|---------|-----------|
| **Upload** | Speed up large file uploads from client to S3 | Multipart upload (parallel parts) |
| **Download** | Speed up large reads by EC2 workers | Parallel byte-range GETs |

### Features

- **Multipart Parallel Upload**: Uploads large files to S3 using multiple parallel parts
- **Parallel Byte-Range Downloads**: Multiple EC2 workers download different byte ranges simultaneously
- **Automated Scheduled Downloads**: EC2 workers automatically download chunks every minute via cron
- **Performance Comparison**: Compare single vs parallel transfer performance
- **Sample Data Generation**: Generate large test files for demonstration

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- Python 3.8+ (for local script execution)
- AWS account with permissions to create:
  - S3 buckets
  - EC2 instances
  - IAM roles and policies
  - Security groups

## Architecture

```plaintext
┌─────────────┐
│   Client    │───Multipart Upload───┐
│  (Local)    │                      │
└─────────────┘                      ▼
                              ┌──────────┐
                              │   S3     │
                              │  Bucket  │
                              └──────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              ┌─────────┐      ┌─────────┐      ┌─────────┐
              │ Worker 1│      │ Worker 2│      │ Worker 3│
              │(Byte 0-N)│      │(Byte N-M)│     │(Byte M-P)│
              └─────────┘      └─────────┘      └─────────┘
```

## Deployment

### 1. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy infrastructure
terraform apply
```

This will create:

- S3 bucket for storing files and scripts
- IAM role with S3 permissions
- Multiple EC2 worker instances (default: 3)
- Security group for EC2 access
- Uploads all Python scripts to S3 `scripts/` prefix

### 2. Configure Variables (Optional)

Edit `variables.tf` or use `-var` flags:

```bash
terraform apply \
  -var="worker_count=5" \
  -var="instance_type=t3.medium" \
  -var="chunk_size_mb=200"
```

Available variables:

- `worker_count`: Number of EC2 worker instances (default: 3)
- `instance_type`: EC2 instance type (default: t3.micro)
- `bucket_name`: S3 bucket name (auto-generated if empty)
- `target_s3_object_key`: Object key to download every minute (default: `demo/large-file.bin`)
- `chunk_size_mb`: Size of each byte range chunk in MB (default: 100)

## Usage

### Step-by-step demo flow

1. **Generate sample data (optional)**

   ```bash
   cd scripts
   python3 generate_sample_data.py --size-gb 1 --output large-file.bin
   ```

2. **Upload with multipart parallel upload (demonstrates faster uploads)**

   ```bash
   python3 upload_multipart.py \
     --file large-file.bin \
     --bucket <bucket-name> \
     --key demo/large-file.bin \
     --part-size-mb 10 \
     --max-workers 5
   ```

3. **Workers automatically download chunks every minute**

   Workers run without public IP addresses. Use AWS Systems Manager Session Manager to inspect them:

   ```bash
   # Get worker instance IDs
   terraform output worker_instance_ids

   # Start a session (replace <instance-id>)
   aws ssm start-session --target <instance-id> --region <region>

   # Inside the session, tail the log
   sudo tail -f /var/log/s3-download.log
   ```

4. **(Optional) Compare client-side downloads**

   ```bash
   python3 download_parallel.py \
     --bucket <bucket-name> \
     --key demo/large-file.bin \
     --output downloaded-file.bin \
     --workers 3 \
     --chunk-size-mb 100 \
     --compare
   ```

Example log output:

```plaintext
2024-01-15 10:00:01 Worker 0: Downloaded bytes 0-104857599 (104,857,600 bytes) in 2.34s (42.75 MB/s) -> /tmp/s3-chunks/chunk-0-1705296001.bin
2024-01-15 10:00:02 Worker 1: Downloaded bytes 104857600-209715199 (104,857,600 bytes) in 2.41s (41.52 MB/s) -> /tmp/s3-chunks/chunk-1-1705296002.bin
2024-01-15 10:00:03 Worker 2: Downloaded bytes 209715200-314572799 (104,857,600 bytes) in 2.38s (42.02 MB/s) -> /tmp/s3-chunks/chunk-2-1705296003.bin
```

### Run Full Demo Workflow

Orchestrate the complete demo:

```bash
python3 compare_performance.py \
  --bucket <bucket-name> \
  --size-gb 1.0 \
  --key demo/large-file.bin \
  --upload-workers 5 \
  --download-workers 3
```

## Performance Metrics

The scripts output performance metrics including:

- **Elapsed Time**: Total transfer time in seconds
- **Throughput**: Transfer speed in MB/s
- **Speedup Factor**: Improvement over single transfer (when using `--compare`)

Example output:

```plaintext
PERFORMANCE COMPARISON
============================================================
Single upload:      45.23s (22.12 MB/s)
Multipart parallel: 12.34s (81.04 MB/s)
Speedup:            3.67x
============================================================
```

## Scripts on EC2 Instances

All scripts are automatically downloaded to EC2 instances from S3 during bootstrap. They are located at:

```plaintext
/opt/s3-demo/scripts/
```

Scripts available on workers:

- `worker_download.py` - Runs every minute via cron
- `download_parallel.py` - For manual testing
- `upload_multipart.py` - For manual testing
- `generate_sample_data.py` - For generating test data

## Monitoring

### Check Worker Status

```bash
# List all workers
terraform output worker_instance_ids

# Start an SSM session to a worker
aws ssm start-session --target <instance-id> --region <region>

# Inside the session
crontab -l
sudo tail -20 /var/log/s3-download.log
```

### CloudWatch Metrics

Monitor EC2 instance metrics in AWS CloudWatch:

- Network In/Out
- CPU Utilization
- Status Checks

## Troubleshooting

### Scripts Not Found on EC2

If scripts are missing, check:

1. S3 bucket contains scripts in `scripts/` prefix
2. IAM role has `s3:GetObject` permission
3. User data script completed successfully

Manually download scripts:

```bash
aws ssm start-session --target <instance-id> --region <region>
sudo aws s3 cp s3://<bucket-name>/scripts/ /opt/s3-demo/scripts/ --recursive
```

### Cron Job Not Running

Check cron service:

```bash
aws ssm start-session --target <instance-id> --region <region>
sudo systemctl status crond
crontab -l
```

### Download Errors

Check logs for specific errors:

```bash
aws ssm start-session --target <instance-id> --region <region>
sudo grep ERROR /var/log/s3-download.log
```

Common issues:

- Object doesn't exist in S3
- Byte range out of bounds
- IAM permissions insufficient
- Network connectivity issues

## Cleanup

Destroy all resources:

```bash
terraform destroy
```

This will remove:

- S3 bucket and all objects
- EC2 instances
- IAM roles and policies
- Security groups

**Note**: Make sure to backup any important data before destroying!

## Cost Considerations

- **EC2 Instances**: Charges based on instance type and runtime
- **S3 Storage**: Charges for stored data and requests
- **Data Transfer**: Outbound data transfer charges may apply

To minimize costs:

- Use smaller instance types for testing
- Destroy infrastructure when not in use
- Use smaller test files for development

## Best Practices

1. **Part Size**: Use 5-10 MB parts for multipart uploads (S3 minimum is 5 MB)
2. **Chunk Size**: Balance chunk size with number of workers (larger chunks = fewer requests but less parallelism)
3. **Concurrency**: Adjust worker count based on network bandwidth and instance type
4. **Error Handling**: Scripts include retry logic, but monitor logs for failures
5. **Security**: Use IAM roles with least-privilege permissions

## License

See LICENSE file for details.
