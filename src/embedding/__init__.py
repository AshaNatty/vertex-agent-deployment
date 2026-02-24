"""
Embedding pipeline using Vertex AI text-embedding models.

Generates dense vector embeddings for a list of text documents
and optionally persists them to GCS.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterator

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "textembedding-gecko@003"
_DEFAULT_BATCH = 100


def _chunks(lst: list, size: int) -> Iterator[list]:
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def embed_texts(
    texts: list[str],
    model_name: str | None = None,
    batch_size: int | None = None,
    project: str | None = None,
    location: str | None = None,
) -> list[list[float]]:
    """
    Embed a list of texts using a Vertex AI text-embedding model.

    Returns a list of float vectors, one per input text.
    """
    model_name = model_name or os.environ.get("EMBEDDING_MODEL_NAME", _DEFAULT_MODEL)
    batch_size = batch_size or int(os.environ.get("EMBEDDING_BATCH_SIZE", _DEFAULT_BATCH))
    project = project or os.environ["GCP_PROJECT_ID"]
    location = location or os.environ.get("GCP_REGION", "us-central1")

    from vertexai.language_models import TextEmbeddingModel  # type: ignore

    import vertexai

    vertexai.init(project=project, location=location)
    model = TextEmbeddingModel.from_pretrained(model_name)

    all_embeddings: list[list[float]] = []
    for batch in _chunks(texts, batch_size):
        embeddings = model.get_embeddings(batch)
        all_embeddings.extend([e.values for e in embeddings])
        logger.info("Embedded %d / %d texts", len(all_embeddings), len(texts))

    return all_embeddings


def save_embeddings_to_gcs(
    ids: list[str],
    embeddings: list[list[float]],
    gcs_uri: str,
) -> None:
    """
    Persist embeddings to GCS in JSON Lines format.

    Each line: {"id": "<id>", "embedding": [0.1, 0.2, ...]}
    """
    from google.cloud import storage  # lazy import

    bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    lines = [
        json.dumps({"id": doc_id, "embedding": emb})
        for doc_id, emb in zip(ids, embeddings)
    ]
    blob.upload_from_string("\n".join(lines), content_type="application/jsonl")
    logger.info("Saved %d embeddings to %s", len(embeddings), gcs_uri)


def run_embedding_pipeline(
    texts: list[str],
    ids: list[str],
    output_gcs_uri: str,
    **kwargs,
) -> list[list[float]]:
    """
    End-to-end helper: embed texts, save to GCS, return vectors.
    """
    if len(texts) != len(ids):
        raise ValueError("texts and ids must have the same length")

    embeddings = embed_texts(texts, **kwargs)
    save_embeddings_to_gcs(ids, embeddings, output_gcs_uri)
    return embeddings
