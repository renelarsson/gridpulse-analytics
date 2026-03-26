# Terraform Slice

This directory contains the narrowest Terraform slice that matches the currently validated Step 11 warehouse path.

Current scope:

- create the `iso_ne_raw` BigQuery dataset
- create the service account used for the raw `dlt` BigQuery landing
- grant only the minimum IAM needed for the current raw-loading step

## What This Slice Actually Does

This slice is deliberately small. It does not try to model the entire capstone platform yet.

When you run `terraform plan` or `terraform apply` here, Terraform will manage only these current Step 11 resources:

- one BigQuery dataset for raw warehouse landing
- one service account for the raw loader path
- one project-level IAM binding so that account can create BigQuery jobs
- one dataset-level IAM binding so that account can write into the raw dataset

That means the slice is already useful for reproducibility:

- the same infrastructure can be recreated on another machine
- changes are reviewed as code instead of applied manually in the console
- the repo records exactly which cloud resources belong to the current milestone

It is not the whole infrastructure story yet because the next modeling decisions are still in front of us.

This is intentionally not the full cloud build-out yet. It does not create GCS, dbt jobs, Kestra infrastructure, or dashboard hosting.

## Files

- `versions.tf`: Terraform and provider requirements
- `variables.tf`: project, region, dataset, and service-account inputs
- `main.tf`: BigQuery dataset, service account, and IAM bindings
- `outputs.tf`: key values to reuse after apply
- `terraform.tfvars.example`: copy-and-edit example values

## Usage

```bash
cd infra/terraform
terraform init
cp terraform.tfvars.example terraform.tfvars
terraform plan
terraform apply
```

## Notes

- The default dataset id matches the validated raw landing target: `iso_ne_raw`.
- The default service-account id matches the validated manual Step 11 path: `dbt-bigquery-service-account`.
- The current IAM scope is intentionally narrow:
  - `roles/bigquery.jobUser` on the project
  - `roles/bigquery.dataEditor` on the raw dataset

## Why This Is Still Terraform

Yes, Terraform is meant for reproducible, automated, and version-controlled infrastructure management.

This directory already does that, just for a narrow slice of the platform instead of the whole platform.

The important distinction is scope:

- current scope: only the infrastructure already proven necessary by the validated raw BigQuery landing
- later scope: additional datasets, dbt-related service accounts and IAM, orchestration resources, storage, and possibly deployment resources

## Not Done Yet

- service-account key generation and secret handling
- GCS buckets
- dbt service accounts or separate dbt IAM
- broader project IAM and environment separation