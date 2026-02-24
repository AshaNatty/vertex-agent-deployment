"""Tests for the FastAPI server (no GCP credentials required)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a TestClient with the orchestrator mocked out."""
    with (
        patch("src.endpoint.server.init_vertex"),
        patch("src.endpoint.server.Orchestrator") as mock_orch_cls,
    ):
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        from src.endpoint.server import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_orch


def test_healthz(client):
    c, _ = client
    resp = c.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_predict_no_endpoint_env(client):
    c, _ = client
    import os

    os.environ.pop("VERTEX_AI_ENDPOINT_ID", None)
    resp = c.post("/predict", json={"instances": [{"text": "hello"}]})
    assert resp.status_code == 503


def test_agent_not_found(client):
    c, mock_orch = client

    async def raise_key_error(agent_name, query, context):
        raise KeyError(agent_name)

    mock_orch.run = AsyncMock(side_effect=raise_key_error)

    resp = c.post("/agents/unknown", json={"query": "test"})
    assert resp.status_code == 404
