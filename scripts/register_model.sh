#!/usr/bin/env bash
# register_model.sh – Register a container image as a Vertex AI Model and
#                     deploy it to a Vertex AI online-prediction endpoint.
#
# Usage:
#   ./scripts/register_model.sh [--project PROJECT] [--region REGION] \
#                               [--image IMAGE_URI] [--endpoint-name NAME]

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
REPO="${ARTIFACT_REGISTRY_REPO:-vertex-agents}"
IMAGE_NAME_VAR="${IMAGE_NAME:-vertex-agent}"
TAG="${IMAGE_TAG:-latest}"
ENDPOINT_NAME="${VERTEX_AI_ENDPOINT_NAME:-vertex-agent-endpoint}"
MACHINE_TYPE="n1-standard-4"
MIN_REPLICAS=1
MAX_REPLICAS=5

# ── Argument parsing ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --project)       PROJECT_ID="$2";    shift 2 ;;
    --region)        REGION="$2";        shift 2 ;;
    --image)         FULL_IMAGE="$2";    shift 2 ;;
    --endpoint-name) ENDPOINT_NAME="$2"; shift 2 ;;
    --machine-type)  MACHINE_TYPE="$2";  shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: GCP_PROJECT_ID is not set." >&2
  exit 1
fi

FULL_IMAGE="${FULL_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME_VAR}:${TAG}}"

echo "==> Registering model in Vertex AI Model Registry…"
MODEL_RESOURCE=$(gcloud ai models upload \
  --region="${REGION}" \
  --display-name="vertex-agent-$(date +%Y%m%d%H%M%S)" \
  --container-image-uri="${FULL_IMAGE}" \
  --container-predict-route="/predict" \
  --container-health-route="/healthz" \
  --container-ports=8080 \
  --project="${PROJECT_ID}" \
  --format="value(model)")

echo "   Model resource: ${MODEL_RESOURCE}"

echo "==> Getting or creating endpoint: ${ENDPOINT_NAME}…"
ENDPOINT_ID=$(gcloud ai endpoints list \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --filter="displayName=${ENDPOINT_NAME}" \
  --format="value(name)" | head -n 1)

if [[ -z "${ENDPOINT_ID}" ]]; then
  echo "   Creating new endpoint…"
  ENDPOINT_ID=$(gcloud ai endpoints create \
    --region="${REGION}" \
    --display-name="${ENDPOINT_NAME}" \
    --project="${PROJECT_ID}" \
    --format="value(name)")
fi
echo "   Endpoint: ${ENDPOINT_ID}"

echo "==> Deploying model to endpoint…"
gcloud ai endpoints deploy-model "${ENDPOINT_ID}" \
  --region="${REGION}" \
  --model="${MODEL_RESOURCE}" \
  --display-name="vertex-agent-deployed" \
  --machine-type="${MACHINE_TYPE}" \
  --min-replica-count="${MIN_REPLICAS}" \
  --max-replica-count="${MAX_REPLICAS}" \
  --traffic-split=0=100 \
  --project="${PROJECT_ID}"

echo "==> Model registered and deployed successfully."
echo "    Endpoint ID: ${ENDPOINT_ID}"
