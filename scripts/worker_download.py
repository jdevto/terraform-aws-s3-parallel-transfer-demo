#!/usr/bin/env python3
"""
Worker script to download a specific byte range from S3.
Runs on each EC2 worker instance via cron every minute.
"""
import argparse
import boto3
import os
import sys
import time
from botocore.exceptions import ClientError

def download_byte_range(s3_client, bucket, key, start_byte, end_byte, output_path):
    """Download a specific byte range from S3."""
    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f'bytes={start_byte}-{end_byte}'
        )

        # Get content length
        content_length = int(response.get('ContentLength', 0))

        # Download data
        data = response['Body'].read()

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(data)

        return content_length, True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'InvalidRange':
            # Range might be out of bounds, return 0
            return 0, False
        raise

def main():
    parser = argparse.ArgumentParser(description='Download byte range from S3')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--object-key', type=str, required=True, help='S3 object key')
    parser.add_argument('--worker-id', type=int, required=True, help='Worker ID (0-based)')
    parser.add_argument('--total-workers', type=int, required=True, help='Total number of workers')
    parser.add_argument('--chunk-size-mb', type=int, default=100, help='Chunk size per worker in MB (default: 100)')

    args = parser.parse_args()

    # Initialize S3 client
    s3_client = boto3.client('s3')

    # Get object size
    try:
        response = s3_client.head_object(Bucket=args.bucket, Key=args.object_key)
        object_size = response['ContentLength']
    except ClientError as e:
        log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} ERROR: Failed to get object metadata: {e}"
        print(log_message)
        with open('/var/log/s3-download.log', 'a') as log:
            log.write(log_message + '\n')
        sys.exit(1)

    # Calculate byte range for this worker
    chunk_size = args.chunk_size_mb * 1024 * 1024
    start_byte = args.worker_id * chunk_size
    end_byte = min(start_byte + chunk_size - 1, object_size - 1)

    # Skip if start_byte is beyond object size
    if start_byte >= object_size:
        log_message = f"{time.strftime('%Y-%m-%d %H:%M:%S')} Worker {args.worker_id}: Skipped (start_byte {start_byte} >= object_size {object_size})"
        print(log_message)
        with open('/var/log/s3-download.log', 'a') as log:
            log.write(log_message + '\n')
        sys.exit(0)

    # Output path
    output_dir = '/tmp/s3-chunks'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time())
    output_path = f"{output_dir}/chunk-{args.worker_id}-{timestamp}.bin"

    # Download
    start_time = time.time()
    try:
        bytes_downloaded, success = download_byte_range(
            s3_client, args.bucket, args.object_key,
            start_byte, end_byte, output_path
        )

        elapsed = time.time() - start_time

        if success and bytes_downloaded > 0:
            throughput = (bytes_downloaded / elapsed) / (1024 * 1024) if elapsed > 0 else 0
            log_message = (
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} Worker {args.worker_id}: "
                f"Downloaded bytes {start_byte}-{end_byte} ({bytes_downloaded:,} bytes) "
                f"in {elapsed:.2f}s ({throughput:.2f} MB/s) -> {output_path}"
            )
        else:
            log_message = (
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} Worker {args.worker_id}: "
                f"No data downloaded (range {start_byte}-{end_byte} may be out of bounds)"
            )

        print(log_message)
        with open('/var/log/s3-download.log', 'a') as log:
            log.write(log_message + '\n')

    except Exception as e:
        elapsed = time.time() - start_time
        log_message = (
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} Worker {args.worker_id}: "
            f"ERROR downloading bytes {start_byte}-{end_byte}: {e}"
        )
        print(log_message, file=sys.stderr)
        with open('/var/log/s3-download.log', 'a') as log:
            log.write(log_message + '\n')
        sys.exit(1)

if __name__ == '__main__':
    main()
