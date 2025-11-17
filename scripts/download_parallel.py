#!/usr/bin/env python3
"""
Demonstrate parallel byte-range downloads from S3.
Compares performance between single download and parallel byte-range downloads.
"""
import argparse
import boto3
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

def single_download(s3_client, bucket, key, output_path):
    """Download file using single GET operation."""
    print(f"Starting single download: s3://{bucket}/{key} -> {output_path}")
    start_time = time.time()

    try:
        # Get object size first
        response = s3_client.head_object(Bucket=bucket, Key=key)
        object_size = response['ContentLength']

        # Download
        s3_client.download_file(bucket, key, output_path)

        elapsed = time.time() - start_time
        throughput = (object_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0

        print(f"Single download completed:")
        print(f"  Size: {object_size:,} bytes ({object_size / (1024*1024*1024):.2f} GB)")
        print(f"  Time: {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.2f} MB/s")
        return elapsed, throughput
    except Exception as e:
        print(f"Error during single download: {e}", file=sys.stderr)
        return None, None

def download_chunk(s3_client, bucket, key, start_byte, end_byte, chunk_path):
    """Download a specific byte range chunk."""
    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f'bytes={start_byte}-{end_byte}'
        )

        data = response['Body'].read()

        with open(chunk_path, 'wb') as f:
            f.write(data)

        return len(data), True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'InvalidRange':
            return 0, False
        raise

def parallel_download(s3_client, bucket, key, output_path, num_workers=3, chunk_size_mb=100):
    """Download file using parallel byte-range GETs."""
    print(f"Starting parallel download: s3://{bucket}/{key} -> {output_path}")
    print(f"  Workers: {num_workers}")
    print(f"  Chunk size: {chunk_size_mb} MB")

    start_time = time.time()

    try:
        # Get object size
        response = s3_client.head_object(Bucket=bucket, Key=key)
        object_size = response['ContentLength']
        print(f"  Object size: {object_size:,} bytes ({object_size / (1024*1024*1024):.2f} GB)")

        # Calculate chunks
        chunk_size = chunk_size_mb * 1024 * 1024
        num_chunks = (object_size + chunk_size - 1) // chunk_size

        print(f"  Total chunks: {num_chunks}")

        # Create temp directory for chunks
        temp_dir = f"{output_path}.chunks"
        os.makedirs(temp_dir, exist_ok=True)

        chunks = []
        completed = 0

        # Download chunks in parallel
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for i in range(num_chunks):
                start_byte = i * chunk_size
                end_byte = min(start_byte + chunk_size - 1, object_size - 1)
                chunk_path = f"{temp_dir}/chunk-{i}.bin"

                future = executor.submit(
                    download_chunk, s3_client, bucket, key,
                    start_byte, end_byte, chunk_path
                )
                futures.append((i, start_byte, end_byte, chunk_path, future))

            # Collect results
            chunk_results = []
            for i, start_byte, end_byte, chunk_path, future in futures:
                try:
                    bytes_downloaded, success = future.result()
                    chunk_results.append((i, chunk_path, bytes_downloaded, success))
                    completed += 1
                    progress = (completed / num_chunks) * 100
                    print(f"  Progress: {progress:.1f}% ({completed}/{num_chunks} chunks)", end='\r')
                except Exception as e:
                    print(f"\nError downloading chunk {i}: {e}", file=sys.stderr)
                    raise

        print()  # New line after progress

        # Sort chunks by index
        chunk_results.sort(key=lambda x: x[0])

        # Combine chunks
        print(f"  Combining {len(chunk_results)} chunks...")
        with open(output_path, 'wb') as outfile:
            for i, chunk_path, bytes_downloaded, success in chunk_results:
                if success and bytes_downloaded > 0:
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(chunk_path)

        # Cleanup temp directory
        os.rmdir(temp_dir)

        elapsed = time.time() - start_time
        throughput = (object_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0

        print(f"Parallel download completed:")
        print(f"  Time: {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.2f} MB/s")
        print(f"  Chunks downloaded: {len(chunk_results)}")
        return elapsed, throughput

    except Exception as e:
        print(f"Error during parallel download: {e}", file=sys.stderr)
        return None, None

def main():
    parser = argparse.ArgumentParser(description='Download file from S3 using parallel byte-range GETs')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--key', type=str, required=True, help='S3 object key')
    parser.add_argument('--output', type=str, required=True, help='Output file path')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--chunk-size-mb', type=int, default=100, help='Chunk size in MB (default: 100)')
    parser.add_argument('--compare', action='store_true', help='Compare with single download')

    args = parser.parse_args()

    s3_client = boto3.client('s3')

    # Compare mode
    if args.compare:
        print("=" * 60)
        print("COMPARISON MODE")
        print("=" * 60)
        print()

        # Single download
        single_time, single_throughput = single_download(
            s3_client, args.bucket, args.key, f"{args.output}.single"
        )
        print()

        # Parallel download
        parallel_time, parallel_throughput = parallel_download(
            s3_client, args.bucket, args.key, args.output,
            args.workers, args.chunk_size_mb
        )
        print()

        # Comparison
        if single_time and parallel_time:
            speedup = single_time / parallel_time
            print("=" * 60)
            print("PERFORMANCE COMPARISON")
            print("=" * 60)
            print(f"Single download:    {single_time:.2f}s ({single_throughput:.2f} MB/s)")
            print(f"Parallel download:  {parallel_time:.2f}s ({parallel_throughput:.2f} MB/s)")
            print(f"Speedup:            {speedup:.2f}x")
            print("=" * 60)
    else:
        # Just parallel download
        parallel_download(
            s3_client, args.bucket, args.key, args.output,
            args.workers, args.chunk_size_mb
        )

if __name__ == '__main__':
    main()
