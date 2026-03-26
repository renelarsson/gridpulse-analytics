output "raw_dataset_id" {
  description = "BigQuery raw dataset id."
  value       = google_bigquery_dataset.iso_ne_raw.dataset_id
}

output "raw_dataset_location" {
  description = "BigQuery raw dataset location."
  value       = google_bigquery_dataset.iso_ne_raw.location
}

output "raw_loader_service_account_email" {
  description = "Service account email for the raw loader."
  value       = google_service_account.raw_loader.email
}