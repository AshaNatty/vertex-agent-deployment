#!/usr/bin/env bash
# deploy.sh – Build, push, and deploy the Vertex Agent container image.
#
# Usage:
#   ./scripts/deploy.sh [--project PROJECT_ID] [--region REGION] [--tag TAG]
#
# Environment variables (can be set via .env):
#   GCP_PROJECT_ID, GCP_REGION, ARTIFACT_REGISTRY_REPO, IMAGE_NAME, IMAGE_TAG

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
REPO="${ARTIFACT_REGISTRY_REPO:-vertex-agents}"
IMAGE="${IMAGE_NAME:-vertex-agent}"
TAG="${IMAGE_TAG:-latest}"

# ── Argument parsing ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --region)  REGION="$2";     shift 2 ;;
    --tag)     TAG="$2";        shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: GCP_PROJECT_ID is not set. Export it or pass --project." >&2
  exit 1
fi

FULL_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:${TAG}"

echo "==> Authenticating Docker with Artifact Registry…"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Building image: ${FULL_IMAGE}"
docker build \
  --platform linux/amd64 \
  --tag "${FULL_IMAGE}" \
  --file Dockerfile \
  .

echo "==> Pushing image: ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo "==> Uploading model to Vertex AI Model Registry…"
gcloud ai models upload \
  --region="${REGION}" \
  --display-name="vertex-agent-${TAG}" \
  --container-image-uri="${FULL_IMAGE}" \
  --container-predict-route="/predict" \
  --container-health-route="/healthz" \
  --container-ports=8080 \
  --project="${PROJECT_ID}"

echo "==> Deployment complete. Image: ${FULL_IMAGE}"
