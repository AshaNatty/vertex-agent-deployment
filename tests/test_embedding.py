"""Tests for the embedding pipeline helpers (no GCP credentials required)."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_embeddings(texts: list[str]) -> list:
    """Return mock embedding objects whose .values are simple vectors."""
    mocks = []
    for i, _ in enumerate(texts):
        m = MagicMock()
        m.values = [float(i)] * 4
        mocks.append(m)
    return mocks


def test_chunks_even() -> None:
    from src.embedding import _chunks

    result = list(_chunks([1, 2, 3, 4], 2))
    assert result == [[1, 2], [3, 4]]


def test_chunks_uneven() -> None:
    from src.embedding import _chunks

    result = list(_chunks([1, 2, 3], 2))
    assert result == [[1, 2], [3]]


def test_chunks_larger_than_list() -> None:
    from src.embedding import _chunks

    result = list(_chunks([1, 2], 10))
    assert result == [[1, 2]]


@patch.dict(
    "os.environ",
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_REGION": "us-central1",
        "EMBEDDING_MODEL_NAME": "textembedding-gecko@003",
        "EMBEDDING_BATCH_SIZE": "2",
    },
)
def test_embed_texts_calls_model() -> None:
    vertexai_mock = MagicMock()
    mock_model_cls = MagicMock()
    mock_instance = MagicMock()
    mock_model_cls.from_pretrained.return_value = mock_instance
    mock_instance.get_embeddings.side_effect = lambda batch: _make_mock_embeddings(batch)
    vertexai_mock.language_models.TextEmbeddingModel = mock_model_cls

    import sys

    sys.modules.setdefault("vertexai", vertexai_mock)
    sys.modules.setdefault("vertexai.language_models", vertexai_mock.language_models)

    from src.embedding import embed_texts

    with patch("vertexai.init", vertexai_mock.init):
        result = embed_texts(["a", "b", "c"])

    assert len(result) == 3
    assert all(isinstance(v, list) for v in result)


def test_run_embedding_pipeline_length_mismatch_raises() -> None:
    from src.embedding import run_embedding_pipeline

    with pytest.raises(ValueError, match="same length"):
        run_embedding_pipeline(
            texts=["a", "b"],
            ids=["id1"],
            output_gcs_uri="gs://bucket/path",
        )


def test_save_embeddings_to_gcs(tmp_path) -> None:
    """Verify the GCS save logic writes valid JSON lines."""
    import sys
    import types

    ids = ["doc1", "doc2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    mock_storage_mod = types.ModuleType("google.cloud.storage")
    mock_storage_mod.Client = MagicMock(return_value=mock_client)

    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    cloud_mod.storage = mock_storage_mod

    with (
        patch.dict(
            sys.modules,
            {
                "google": google_mod,
                "google.cloud": cloud_mod,
                "google.cloud.storage": mock_storage_mod,
            },
        )
    ):
        from src.embedding import save_embeddings_to_gcs

        save_embeddings_to_gcs(ids, embeddings, "gs://bucket/output.jsonl")

    uploaded = mock_blob.upload_from_string.call_args[0][0]
    lines = uploaded.strip().split("\n")
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["id"] == "doc1"
    assert parsed[1]["embedding"] == [0.3, 0.4]
