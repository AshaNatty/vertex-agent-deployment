terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "vertex-agent-deployment/terraform.tfstate"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ── Enable required APIs ──────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── GCS Buckets ───────────────────────────────────────────────

resource "google_storage_bucket" "staging" {
  name                        = "${var.project_id}-vertex-staging"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket" "pipelines" {
  name                        = "${var.project_id}-vertex-pipelines"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

# ── Artifact Registry ─────────────────────────────────────────

resource "google_artifact_registry_repository" "agents" {
  provider      = google-beta
  repository_id = var.artifact_registry_repo
  format        = "DOCKER"
  location      = var.region
  description   = "Docker images for Vertex AI agents"

  depends_on = [google_project_service.apis]
}

# ── Service Account ───────────────────────────────────────────

resource "google_service_account" "vertex_agent_sa" {
  account_id   = "vertex-agent-sa"
  display_name = "Vertex Agent Service Account"
}

resource "google_project_iam_member" "vertex_agent_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/storage.objectAdmin",
    "roles/artifactregistry.reader",
    "roles/bigquery.dataEditor",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.vertex_agent_sa.email}"
}

# ── Vertex AI Matching Engine Index ───────────────────────────

resource "google_vertex_ai_index" "agent_index" {
  provider     = google-beta
  display_name = var.matching_engine_index_name
  region       = var.region
  description  = "Vector search index for agent retrieval"

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.staging.name}/matching-engine/initial/"
    config {
      dimensions                  = var.vector_dimensions
      approximate_neighbors_count = 150
      distance_measure_type       = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_vertex_ai_index_endpoint" "agent_endpoint" {
  provider     = google-beta
  display_name = var.matching_engine_endpoint_name
  region       = var.region
  description  = "Public endpoint for agent vector search"

  public_endpoint_enabled = true
  depends_on              = [google_project_service.apis]
}
