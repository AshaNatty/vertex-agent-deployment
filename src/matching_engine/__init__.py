"""
Vertex AI Matching Engine (Vector Search) integration.

Provides helpers to:
  - Create / describe an index
  - Create / describe an index endpoint
  - Deploy an index to an endpoint
  - Run nearest-neighbour queries
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_or_create_index(
    display_name: str,
    dimensions: int | None = None,
    approximate_neighbors_count: int = 150,
    distance_measure_type: str = "DOT_PRODUCT_DISTANCE",
    shard_size: str = "SHARD_SIZE_SMALL",
) -> "aiplatform.MatchingEngineIndex":
    """Return an existing index or create a new approximate nearest-neighbour index."""
    from google.cloud import aiplatform  # lazy import

    dimensions = dimensions or int(os.environ.get("VECTOR_DIMENSIONS", 768))
    existing = aiplatform.MatchingEngineIndex.list(
        filter=f'display_name="{display_name}"'
    )
    if existing:
        logger.info("Found existing index: %s", existing[0].name)
        return existing[0]

    logger.info("Creating Matching Engine index: %s (dims=%d)", display_name, dimensions)
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=display_name,
        dimensions=dimensions,
        approximate_neighbors_count=approximate_neighbors_count,
        distance_measure_type=distance_measure_type,
        leaf_node_embedding_count=500,
        leaf_nodes_to_search_percent=7,
        description=f"Vector search index – {display_name}",
    )
    logger.info("Created index: %s", index.name)
    return index


def get_or_create_index_endpoint(
    display_name: str,
    public_endpoint: bool = True,
) -> "aiplatform.MatchingEngineIndexEndpoint":
    """Return an existing index endpoint or create a new one."""
    from google.cloud import aiplatform  # lazy import

    existing = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{display_name}"'
    )
    if existing:
        logger.info("Found existing index endpoint: %s", existing[0].name)
        return existing[0]

    logger.info("Creating Matching Engine index endpoint: %s", display_name)
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=display_name,
        public_endpoint_enabled=public_endpoint,
    )
    logger.info("Created index endpoint: %s", endpoint.name)
    return endpoint


def deploy_index(
    index: "aiplatform.MatchingEngineIndex",
    endpoint: "aiplatform.MatchingEngineIndexEndpoint",
    deployed_index_id: str,
    machine_type: str = "e2-standard-16",
    min_replica_count: int = 1,
    max_replica_count: int = 5,
) -> None:
    """Deploy a Matching Engine index to an endpoint."""
    logger.info(
        "Deploying index %s to endpoint %s", index.display_name, endpoint.display_name
    )
    endpoint.deploy_index(
        index=index,
        deployed_index_id=deployed_index_id,
        display_name=deployed_index_id,
        machine_type=machine_type,
        min_replica_count=min_replica_count,
        max_replica_count=max_replica_count,
    )
    logger.info("Index deployed: %s", deployed_index_id)


def find_neighbors(
    endpoint_id: str,
    deployed_index_id: str,
    query_embeddings: list[list[float]],
    num_neighbors: int = 10,
    project: str | None = None,
    location: str | None = None,
) -> list[list[dict[str, Any]]]:
    """
    Query the Matching Engine for nearest neighbours.

    Returns a list (one entry per query) of lists of
    {id, distance} dicts.
    """
    from google.cloud import aiplatform  # lazy import

    project = project or os.environ["GCP_PROJECT_ID"]
    location = location or os.environ.get("GCP_REGION", "us-central1")

    endpoint = aiplatform.MatchingEngineIndexEndpoint(
        index_endpoint_name=endpoint_id,
        project=project,
        location=location,
    )
    response = endpoint.find_neighbors(
        deployed_index_id=deployed_index_id,
        queries=query_embeddings,
        num_neighbors=num_neighbors,
    )

    results = []
    for neighbors in response:
        results.append(
            [{"id": n.id, "distance": n.distance} for n in neighbors]
        )
    return results
