variable "project_id" {
  description = "GCP project id for the capstone resources."
  type        = string
}

variable "region" {
  description = "Default GCP region for provider operations."
  type        = string
  default     = "europe-west1"
}

variable "bigquery_location" {
  description = "BigQuery dataset location."
  type        = string
  default     = "EU"
}

variable "raw_dataset_id" {
  description = "BigQuery dataset id for raw ISO-NE landing tables."
  type        = string
  default     = "iso_ne_raw"
}

variable "loader_service_account_id" {
  description = "Account id for the raw-loader service account."
  type        = string
  default     = "dbt-bigquery-service-account"
}

variable "labels" {
  description = "Common labels applied to supported resources."
  type        = map(string)
  default = {
    project = "gridpulse-analytics"
    source  = "iso-ne"
    layer   = "raw"
  }
}