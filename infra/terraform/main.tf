# Google Cloud Platform Infrastructure as Code for Since AI
# Primary Region: europe-north1 (Hamina, Finland)
# Mandatory Data Residency: All storage, compute, and database resources reside in Finland.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "region" {
  type        = string
  default     = "europe-north1"
  description = "Primary GCP Region: europe-north1 (Hamina, Finland)"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Deployment environment (prod / staging)"
}

variable "gemini_flash_model_id" {
  type        = string
  default     = "gemini-1.5-flash-002"
  description = "Configurable Gemini Flash Model ID"
}

variable "gemini_embedding_model_id" {
  type        = string
  default     = "gemini-embedding-001"
  description = "Initial candidate Vertex AI embedding model"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP APIs in europe-north1
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "logging.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry Repository in Finland
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "sinceai-repo"
  description   = "Docker repository for Since AI containers in Finland"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# 3. Secret Manager for Database Credentials
resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "db_secret" {
  secret_id = "sinceai-db-credentials"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "db_secret_version" {
  secret      = google_secret_manager_secret.db_secret.id
  secret_data = random_password.db_password.result
}

# 4. Google Cloud SQL for PostgreSQL 16 (europe-north1)
resource "google_sql_database_instance" "postgres" {
  name             = "sinceai-pg16-${var.environment}"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-custom-2-7680"
    availability_type = "ZONAL" # Local residency within europe-north1
    disk_size         = 20
    disk_type         = "PD_SSD"

    backup_configuration {
      enabled            = true
      location           = var.region # Backups must stay in Finland
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = true
      require_ssl     = true
    }

    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
    }
  }
  deletion_protection = true
  depends_on          = [google_project_service.services]
}

resource "google_sql_database" "database" {
  name     = "sinceai"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = "sinceai_app"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

# 5. Service Account for Cloud Run with Least Privilege
resource "google_service_account" "cloud_run_sa" {
  account_id   = "sinceai-backend-sa"
  display_name = "Since AI Cloud Run Service Account"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  secret_id = google_secret_manager_secret.db_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 6. Cloud Run Backend Service in europe-north1
resource "google_cloud_run_v2_service" "backend" {
  name     = "sinceai-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run_sa.email

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/sinceai-backend:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GEMINI_FLASH_MODEL_ID"
        value = var.gemini_flash_model_id
      }
      env {
        name  = "GEMINI_EMBEDDING_MODEL_ID"
        value = var.gemini_embedding_model_id
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.postgres.connection_name
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_sql_database_instance.postgres,
    google_project_service.services,
  ]
}

# 7. Outputs
output "cloud_run_url" {
  value       = google_cloud_run_v2_service.backend.uri
  description = "Backend REST API endpoint hosted in Hamina, Finland"
}

output "database_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "Cloud SQL PostgreSQL 16 instance in europe-north1"
}
