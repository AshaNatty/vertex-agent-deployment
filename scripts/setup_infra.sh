#!/usr/bin/env bash
# setup_infra.sh – Initialise and apply Terraform infrastructure.
#
# Usage:
#   ./scripts/setup_infra.sh [--project PROJECT] [plan|apply|destroy]

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
ACTION="${1:-plan}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: GCP_PROJECT_ID is not set." >&2
  exit 1
fi

TFVARS_FILE="infra/terraform/terraform.tfvars"
if [[ ! -f "${TFVARS_FILE}" ]]; then
  echo "Warning: ${TFVARS_FILE} not found; copying example file."
  cp "infra/terraform/terraform.tfvars.example" "${TFVARS_FILE}"
  sed -i "s/your-gcp-project-id/${PROJECT_ID}/g" "${TFVARS_FILE}"
fi

cd infra/terraform

echo "==> terraform init"
terraform init

case "${ACTION}" in
  plan)    echo "==> terraform plan"; terraform plan -var-file="terraform.tfvars" ;;
  apply)   echo "==> terraform apply"; terraform apply -var-file="terraform.tfvars" -auto-approve ;;
  destroy) echo "==> terraform destroy"; terraform destroy -var-file="terraform.tfvars" -auto-approve ;;
  *) echo "Unknown action: ${ACTION}. Use plan|apply|destroy." >&2; exit 1 ;;
esac
