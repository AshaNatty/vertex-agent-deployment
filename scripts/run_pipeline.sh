#!/usr/bin/env bash
# run_pipeline.sh – Submit the Vertex AI embedding pipeline job.
#
# Usage:
#   ./scripts/run_pipeline.sh [--project PROJECT] [--region REGION]

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
PIPELINE_ROOT="${VERTEX_AI_PIPELINE_ROOT:-}"
TEMPLATE_PATH="pipelines/vertex_pipeline.yaml"

while [[ $# -gt 0 ]]; do
  case $1 in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --region)  REGION="$2";     shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "${PROJECT_ID}" || -z "${PIPELINE_ROOT}" ]]; then
  echo "Error: GCP_PROJECT_ID and VERTEX_AI_PIPELINE_ROOT must be set." >&2
  exit 1
fi

echo "==> Submitting Vertex AI pipeline…"
python -m src.pipelines --compile-only --output "${TEMPLATE_PATH}"

gcloud ai pipelines run \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --pipeline-root="${PIPELINE_ROOT}" \
  --template-uri="${TEMPLATE_PATH}" \
  --display-name="embedding-pipeline-$(date +%Y%m%d%H%M%S)"

echo "==> Pipeline job submitted."
