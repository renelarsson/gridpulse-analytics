resource "google_bigquery_dataset" "iso_ne_raw" {
  dataset_id                 = var.raw_dataset_id
  friendly_name              = "ISO-NE Raw Landing"
  description                = "Raw ISO-NE landing tables for the de-capstone warehouse path."
  location                   = var.bigquery_location
  delete_contents_on_destroy = false

  labels = var.labels
}

resource "google_service_account" "raw_loader" {
  account_id   = var.loader_service_account_id
  display_name = "de-capstone raw loader"
  description  = "Service account for the validated dlt raw BigQuery landing path."
}

resource "google_project_iam_member" "raw_loader_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.raw_loader.email}"
}

resource "google_bigquery_dataset_iam_member" "raw_loader_dataset_editor" {
  dataset_id = google_bigquery_dataset.iso_ne_raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.raw_loader.email}"
}