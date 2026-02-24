"""
Multi-agent orchestrator.

Routes incoming queries to the correct sub-agent and
aggregates results.  Sub-agents are registered by name.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent:
    """Abstract base class for all sub-agents."""

    name: str = "base"

    async def run(self, query: str, context: dict[str, Any]) -> Any:
        raise NotImplementedError


class RetrievalAgent(BaseAgent):
    """Retrieves relevant documents using Vertex AI Vector Search."""

    name = "retrieval"

    async def run(self, query: str, context: dict[str, Any]) -> Any:
        from src.embedding import embed_texts
        from src.matching_engine import find_neighbors

        import os

        logger.info("[RetrievalAgent] query=%s", query)
        embeddings = embed_texts([query])
        neighbors = find_neighbors(
            endpoint_id=os.environ["MATCHING_ENGINE_INDEX_ENDPOINT_ID"],
            deployed_index_id=os.environ["MATCHING_ENGINE_DEPLOYED_INDEX_ID"],
            query_embeddings=embeddings,
            num_neighbors=context.get("num_neighbors", 5),
        )
        return neighbors[0] if neighbors else []


class SummarisationAgent(BaseAgent):
    """Calls a Vertex AI endpoint to summarise retrieved context."""

    name = "summarisation"

    async def run(self, query: str, context: dict[str, Any]) -> Any:
        from src.endpoint import predict

        import os

        logger.info("[SummarisationAgent] query=%s", query)
        instances = [{"query": query, "documents": context.get("documents", [])}]
        preds = predict(
            endpoint_id=os.environ["VERTEX_AI_ENDPOINT_ID"],
            instances=instances,
        )
        return preds[0] if preds else {}


class RAGAgent(BaseAgent):
    """
    Retrieval-Augmented Generation agent.

    Chains RetrievalAgent → SummarisationAgent.
    """

    name = "rag"

    def __init__(self) -> None:
        self._retrieval = RetrievalAgent()
        self._summarisation = SummarisationAgent()

    async def run(self, query: str, context: dict[str, Any]) -> Any:
        logger.info("[RAGAgent] query=%s", query)
        neighbors = await self._retrieval.run(query, context)
        enriched_context = {**context, "documents": neighbors}
        return await self._summarisation.run(query, enriched_context)


class Orchestrator:
    """
    Central dispatcher: routes requests to registered sub-agents.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        for agent_cls in [RetrievalAgent, SummarisationAgent, RAGAgent]:
            agent = agent_cls()
            self._agents[agent.name] = agent
        logger.info("Orchestrator initialised with agents: %s", list(self._agents))

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    async def run(
        self,
        agent_name: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if agent_name not in self._agents:
            raise KeyError(f"Unknown agent: {agent_name}")
        return await self._agents[agent_name].run(query, context or {})
