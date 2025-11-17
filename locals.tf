locals {
  bucket_name  = "${local.project_name}-${random_id.bucket_suffix.hex}"
  project_name = "s3-parallel-transfer"

  scripts = {
    "requirements.txt"        = "scripts/requirements.txt"
    "worker_download.py"      = "scripts/worker_download.py"
    "download_parallel.py"    = "scripts/download_parallel.py"
    "upload_multipart.py"     = "scripts/upload_multipart.py"
    "generate_sample_data.py" = "scripts/generate_sample_data.py"
    "compare_performance.py"  = "scripts/compare_performance.py"
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}
