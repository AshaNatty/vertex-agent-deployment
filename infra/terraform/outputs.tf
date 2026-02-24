output "staging_bucket" {
  description = "GCS bucket used for Vertex AI staging"
  value       = google_storage_bucket.staging.name
}

output "pipelines_bucket" {
  description = "GCS bucket used for pipeline artifacts"
  value       = google_storage_bucket.pipelines.name
}

output "artifact_registry_url" {
  description = "Docker push URL for the Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}"
}

output "service_account_email" {
  description = "Email of the Vertex Agent service account"
  value       = google_service_account.vertex_agent_sa.email
}

output "matching_engine_index_id" {
  description = "Resource ID of the Matching Engine index"
  value       = google_vertex_ai_index.agent_index.id
}

output "matching_engine_endpoint_id" {
  description = "Resource ID of the Matching Engine index endpoint"
  value       = google_vertex_ai_index_endpoint.agent_endpoint.id
}
