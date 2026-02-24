"""
FastAPI server that acts as the agent prediction endpoint.

Routes:
  GET  /healthz          – liveness probe
  POST /predict          – online prediction via Vertex AI endpoint
  POST /agents/{name}    – route request to a named sub-agent
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any

from src.endpoint import init_vertex, predict
from src.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    init_vertex()
    _orchestrator = Orchestrator()
    logger.info("Server startup complete.")
    yield


app = FastAPI(
    title="Vertex Agent Endpoint",
    description="Enterprise multi-agent serving layer on Vertex AI",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ────────────────────────────────


class PredictRequest(BaseModel):
    instances: list[dict[str, Any]]


class PredictResponse(BaseModel):
    predictions: list[Any]


class AgentRequest(BaseModel):
    query: str
    context: dict[str, Any] = {}


class AgentResponse(BaseModel):
    agent: str
    result: Any


# ── Routes ───────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
async def predict_endpoint(body: PredictRequest) -> PredictResponse:
    endpoint_id = os.environ.get("VERTEX_AI_ENDPOINT_ID", "")
    if not endpoint_id:
        raise HTTPException(status_code=503, detail="VERTEX_AI_ENDPOINT_ID not set")
    try:
        preds = predict(endpoint_id=endpoint_id, instances=body.instances)
        return PredictResponse(predictions=preds)
    except Exception as exc:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/agents/{agent_name}", response_model=AgentResponse)
async def run_agent(agent_name: str, body: AgentRequest) -> AgentResponse:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")
    try:
        result = await _orchestrator.run(
            agent_name=agent_name,
            query=body.query,
            context=body.context,
        )
        return AgentResponse(agent=agent_name, result=result)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    except Exception as exc:
        logger.exception("Agent error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
