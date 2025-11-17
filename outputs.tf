output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.demo.id
}

output "worker_instance_ids" {
  description = "EC2 worker instance IDs (use with SSM Session Manager)"
  value       = aws_instance.workers[*].id
}

output "target_object_key" {
  description = "Target S3 object key for downloads"
  value       = var.target_s3_object_key
}

output "instructions" {
  description = "Instructions for running the demo"
  value       = <<-EOT
    Demo Setup Complete!

    1. Generate sample data (if needed):
       python3 scripts/generate_sample_data.py --size-gb 1 --output large-file.bin

    2. Upload file to S3 using multipart parallel upload:
       python3 scripts/upload_multipart.py --file large-file.bin --bucket ${aws_s3_bucket.demo.id} --key ${var.target_s3_object_key}

    3. Workers automatically download chunks every minute.
       Check logs on each instance via SSM (then run: sudo tail -f /var/log/s3-download.log):
${join("", [for id in aws_instance.workers[*].id : "       aws ssm start-session --target ${id} --region ${var.region}\n"])}
  EOT
}
