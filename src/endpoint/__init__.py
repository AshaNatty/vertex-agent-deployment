"""
Vertex AI Endpoint integration.

Provides helpers to create, update and query a Vertex AI
online-prediction endpoint.
"""
from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


def init_vertex(project: str | None = None, location: str | None = None) -> None:
    """Initialise the Vertex AI SDK with project and region."""
    from google.cloud import aiplatform  # lazy import

    project = project or os.environ["GCP_PROJECT_ID"]
    location = location or os.environ.get("GCP_REGION", "us-central1")
    staging_bucket = os.environ.get("VERTEX_AI_STAGING_BUCKET", "")
    aiplatform.init(
        project=project,
        location=location,
        staging_bucket=staging_bucket,
    )
    logger.info("Vertex AI initialised: project=%s location=%s", project, location)


def get_or_create_endpoint(display_name: str) -> "aiplatform.Endpoint":
    """Return an existing endpoint by display name or create a new one."""
    from google.cloud import aiplatform  # lazy import

    endpoints = aiplatform.Endpoint.list(filter=f'display_name="{display_name}"')
    if endpoints:
        logger.info("Found existing endpoint: %s", endpoints[0].name)
        return endpoints[0]

    logger.info("Creating new endpoint: %s", display_name)
    endpoint = aiplatform.Endpoint.create(display_name=display_name)
    logger.info("Created endpoint: %s", endpoint.name)
    return endpoint


def deploy_model_to_endpoint(
    endpoint: "aiplatform.Endpoint",
    model: "aiplatform.Model",
    machine_type: str = "n1-standard-4",
    min_replica_count: int = 1,
    max_replica_count: int = 5,
    traffic_percentage: int = 100,
) -> None:
    """Deploy a registered model to an endpoint with auto-scaling."""
    logger.info(
        "Deploying model %s to endpoint %s", model.display_name, endpoint.display_name
    )
    endpoint.deploy(
        model=model,
        deployed_model_display_name=model.display_name,
        machine_type=machine_type,
        min_replica_count=min_replica_count,
        max_replica_count=max_replica_count,
        traffic_percentage=traffic_percentage,
        sync=True,
    )
    logger.info("Deployment complete.")


def predict(
    endpoint_id: str,
    instances: list[dict[str, Any]],
    project: str | None = None,
    location: str | None = None,
) -> list[Any]:
    """Run online prediction against a deployed endpoint."""
    from google.cloud import aiplatform  # lazy import

    project = project or os.environ["GCP_PROJECT_ID"]
    location = location or os.environ.get("GCP_REGION", "us-central1")
    endpoint = aiplatform.Endpoint(
        endpoint_name=endpoint_id,
        project=project,
        location=location,
    )
    response = endpoint.predict(instances=instances)
    return response.predictions
