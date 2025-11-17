#!/usr/bin/env python3
"""
Generate large sample data files for S3 transfer demo.
"""
import argparse
import os
import sys
import time

def generate_file(output_path, size_gb):
    """Generate a binary file of specified size."""
    chunk_size = 1024 * 1024  # 1 MB chunks
    total_bytes = int(size_gb * 1024 * 1024 * 1024)
    bytes_written = 0

    print(f"Generating {size_gb} GB file: {output_path}")
    print(f"Total size: {total_bytes:,} bytes")

    start_time = time.time()

    with open(output_path, 'wb') as f:
        chunk = os.urandom(chunk_size)
        while bytes_written < total_bytes:
            write_size = min(chunk_size, total_bytes - bytes_written)
            f.write(chunk[:write_size])
            bytes_written += write_size

            if bytes_written % (100 * 1024 * 1024) == 0:  # Every 100 MB
                progress = (bytes_written / total_bytes) * 100
                elapsed = time.time() - start_time
                speed = bytes_written / elapsed / (1024 * 1024) if elapsed > 0 else 0
                print(f"Progress: {progress:.1f}% ({bytes_written / (1024*1024*1024):.2f} GB) - {speed:.2f} MB/s", end='\r')

    elapsed = time.time() - start_time
    file_size = os.path.getsize(output_path)
    speed = file_size / elapsed / (1024 * 1024) if elapsed > 0 else 0

    print(f"\nFile generated successfully!")
    print(f"  Path: {output_path}")
    print(f"  Size: {file_size:,} bytes ({file_size / (1024*1024*1024):.2f} GB)")
    print(f"  Time: {elapsed:.2f} seconds")
    print(f"  Speed: {speed:.2f} MB/s")

def main():
    parser = argparse.ArgumentParser(description='Generate large sample data files')
    parser.add_argument('--size-gb', type=float, default=1.0, help='File size in GB (default: 1.0)')
    parser.add_argument('--output', type=str, default='large-file.bin', help='Output file path (default: large-file.bin)')

    args = parser.parse_args()

    if args.size_gb <= 0:
        print("Error: Size must be greater than 0", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(args.output):
        response = input(f"File {args.output} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    try:
        generate_file(args.output, args.size_gb)
    except KeyboardInterrupt:
        print("\n\nGeneration interrupted. Cleaning up...")
        if os.path.exists(args.output):
            os.remove(args.output)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
