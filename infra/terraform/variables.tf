variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "artifact_registry_repo" {
  description = "Name of the Artifact Registry Docker repository"
  type        = string
  default     = "vertex-agents"
}

variable "matching_engine_index_name" {
  description = "Display name for the Matching Engine index"
  type        = string
  default     = "agent-vector-index"
}

variable "matching_engine_endpoint_name" {
  description = "Display name for the Matching Engine index endpoint"
  type        = string
  default     = "agent-vector-endpoint"
}

variable "vector_dimensions" {
  description = "Embedding vector dimensionality"
  type        = number
  default     = 768
}
