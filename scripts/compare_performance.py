#!/usr/bin/env python3
"""
Orchestrator script to run the full demo workflow:
1. Generate sample data
2. Upload with multipart parallel upload
3. Download with parallel byte-range GETs
4. Compare performance metrics
"""
import argparse
import subprocess
import sys
import os
import tempfile

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"Error: {description} failed with exit code {result.returncode}", file=sys.stderr)
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description='Orchestrate full S3 parallel transfer demo')
    parser.add_argument('--size-gb', type=float, default=1.0, help='File size in GB (default: 1.0)')
    parser.add_argument('--bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--key', type=str, default='demo/large-file.bin', help='S3 object key (default: demo/large-file.bin)')
    parser.add_argument('--part-size-mb', type=int, default=10, help='Part size for upload in MB (default: 10)')
    parser.add_argument('--upload-workers', type=int, default=5, help='Upload parallel workers (default: 5)')
    parser.add_argument('--download-workers', type=int, default=3, help='Download parallel workers (default: 3)')
    parser.add_argument('--chunk-size-mb', type=int, default=100, help='Download chunk size in MB (default: 100)')
    parser.add_argument('--skip-generate', action='store_true', help='Skip data generation (use existing file)')
    parser.add_argument('--input-file', type=str, help='Input file path (if not generating)')

    args = parser.parse_args()

    # Determine input file
    if args.skip_generate and args.input_file:
        input_file = args.input_file
        if not os.path.exists(input_file):
            print(f"Error: Input file not found: {input_file}", file=sys.stderr)
            sys.exit(1)
    else:
        # Generate sample data
        input_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin').name
        if not run_command(
            [sys.executable, 'generate_sample_data.py', '--size-gb', str(args.size_gb), '--output', input_file],
            'Generating sample data'
        ):
            sys.exit(1)

    # Upload with multipart parallel
    if not run_command(
        [sys.executable, 'upload_multipart.py',
         '--file', input_file,
         '--bucket', args.bucket,
         '--key', args.key,
         '--part-size-mb', str(args.part_size_mb),
         '--max-workers', str(args.upload_workers),
         '--compare'],
        'Uploading with multipart parallel upload (with comparison)'
    ):
        sys.exit(1)

    # Download with parallel byte-range GETs
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bin').name
    if not run_command(
        [sys.executable, 'download_parallel.py',
         '--bucket', args.bucket,
         '--key', args.key,
         '--output', output_file,
         '--workers', str(args.download_workers),
         '--chunk-size-mb', str(args.chunk_size_mb),
         '--compare'],
        'Downloading with parallel byte-range GETs (with comparison)'
    ):
        sys.exit(1)

    # Verify file integrity (optional)
    print(f"\n{'='*60}")
    print("Verification")
    print(f"{'='*60}")
    input_size = os.path.getsize(input_file)
    output_size = os.path.getsize(output_file)

    if input_size == output_size:
        print(f"✓ File sizes match: {input_size:,} bytes")
    else:
        print(f"✗ File size mismatch!")
        print(f"  Input:  {input_size:,} bytes")
        print(f"  Output: {output_size:,} bytes")

    # Cleanup
    if not args.skip_generate:
        os.remove(input_file)
    os.remove(output_file)

    print(f"\n{'='*60}")
    print("Demo completed successfully!")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
