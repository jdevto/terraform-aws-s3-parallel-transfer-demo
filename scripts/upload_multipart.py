#!/usr/bin/env python3
"""
Demonstrate multipart upload with parallel parts to S3.
Compares performance between single upload and multipart parallel upload.
"""
import argparse
import boto3
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

def single_upload(s3_client, bucket, key, file_path):
    """Upload file using single PUT operation."""
    print(f"Starting single upload: {file_path} -> s3://{bucket}/{key}")
    start_time = time.time()

    try:
        file_size = os.path.getsize(file_path)
        s3_client.upload_file(file_path, bucket, key)
        elapsed = time.time() - start_time
        throughput = (file_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0

        print(f"Single upload completed:")
        print(f"  Time: {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.2f} MB/s")
        return elapsed, throughput
    except Exception as e:
        print(f"Error during single upload: {e}", file=sys.stderr)
        return None, None

def upload_part(s3_client, bucket, key, upload_id, part_number, file_path, start_byte, end_byte):
    """Upload a single part of a multipart upload."""
    try:
        with open(file_path, 'rb') as f:
            f.seek(start_byte)
            data = f.read(end_byte - start_byte + 1)

        response = s3_client.upload_part(
            Bucket=bucket,
            Key=key,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=data
        )
        return {
            'PartNumber': part_number,
            'ETag': response['ETag']
        }
    except Exception as e:
        print(f"Error uploading part {part_number}: {e}", file=sys.stderr)
        raise

def multipart_upload_parallel(s3_client, bucket, key, file_path, part_size_mb=10, max_workers=5):
    """Upload file using multipart upload with parallel parts."""
    print(f"Starting multipart parallel upload: {file_path} -> s3://{bucket}/{key}")
    print(f"  Part size: {part_size_mb} MB")
    print(f"  Max workers: {max_workers}")

    start_time = time.time()
    file_size = os.path.getsize(file_path)
    part_size = part_size_mb * 1024 * 1024
    min_part_size = 5 * 1024 * 1024  # 5 MB minimum

    if part_size < min_part_size:
        part_size = min_part_size
        print(f"  Adjusted part size to minimum: {part_size / (1024*1024):.1f} MB")

    # Calculate number of parts
    num_parts = (file_size + part_size - 1) // part_size

    try:
        # Initiate multipart upload
        response = s3_client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = response['UploadId']
        print(f"  Created multipart upload: {upload_id}")
        print(f"  Total parts: {num_parts}")

        parts = []

        # Upload parts in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(num_parts):
                start_byte = i * part_size
                end_byte = min(start_byte + part_size - 1, file_size - 1)
                part_number = i + 1

                future = executor.submit(
                    upload_part, s3_client, bucket, key, upload_id,
                    part_number, file_path, start_byte, end_byte
                )
                futures.append((part_number, future))

            # Collect results as they complete
            completed = 0
            for part_number, future in futures:
                try:
                    part = future.result()
                    parts.append(part)
                    completed += 1
                    progress = (completed / num_parts) * 100
                    print(f"  Progress: {progress:.1f}% ({completed}/{num_parts} parts)", end='\r')
                except Exception as e:
                    print(f"\nError in part {part_number}: {e}", file=sys.stderr)
                    # Abort multipart upload
                    s3_client.abort_multipart_upload(
                        Bucket=bucket, Key=key, UploadId=upload_id
                    )
                    raise

        print()  # New line after progress

        # Sort parts by part number
        parts.sort(key=lambda x: x['PartNumber'])

        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )

        elapsed = time.time() - start_time
        throughput = (file_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0

        print(f"Multipart parallel upload completed:")
        print(f"  Time: {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.2f} MB/s")
        print(f"  Parts uploaded: {num_parts}")
        return elapsed, throughput

    except Exception as e:
        print(f"Error during multipart upload: {e}", file=sys.stderr)
        # Try to abort if upload_id exists
        try:
            if 'upload_id' in locals():
                s3_client.abort_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id
                )
        except:
            pass
        return None, None

def main():
    parser = argparse.ArgumentParser(description='Upload file to S3 using multipart parallel upload')
    parser.add_argument('--file', type=str, required=True, help='File path to upload')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--key', type=str, required=True, help='S3 object key')
    parser.add_argument('--part-size-mb', type=int, default=10, help='Part size in MB (default: 10)')
    parser.add_argument('--max-workers', type=int, default=5, help='Max parallel workers (default: 5)')
    parser.add_argument('--compare', action='store_true', help='Compare with single upload')

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    file_size = os.path.getsize(args.file)
    print(f"File: {args.file}")
    print(f"Size: {file_size:,} bytes ({file_size / (1024*1024*1024):.2f} GB)")
    print()

    s3_client = boto3.client('s3')

    # Compare mode
    if args.compare:
        print("=" * 60)
        print("COMPARISON MODE")
        print("=" * 60)
        print()

        # Single upload
        single_time, single_throughput = single_upload(
            s3_client, args.bucket, f"{args.key}.single", args.file
        )
        print()

        # Multipart parallel upload
        multipart_time, multipart_throughput = multipart_upload_parallel(
            s3_client, args.bucket, args.key, args.file,
            args.part_size_mb, args.max_workers
        )
        print()

        # Comparison
        if single_time and multipart_time:
            speedup = single_time / multipart_time
            print("=" * 60)
            print("PERFORMANCE COMPARISON")
            print("=" * 60)
            print(f"Single upload:      {single_time:.2f}s ({single_throughput:.2f} MB/s)")
            print(f"Multipart parallel: {multipart_time:.2f}s ({multipart_throughput:.2f} MB/s)")
            print(f"Speedup:            {speedup:.2f}x")
            print("=" * 60)
    else:
        # Just multipart upload
        multipart_upload_parallel(
            s3_client, args.bucket, args.key, args.file,
            args.part_size_mb, args.max_workers
        )

if __name__ == '__main__':
    main()
