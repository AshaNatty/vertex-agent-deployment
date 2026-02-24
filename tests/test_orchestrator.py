"""Tests for the agent orchestrator (no GCP credentials required)."""
from __future__ import annotations

import pytest

from src.agents.orchestrator import BaseAgent, Orchestrator


class EchoAgent(BaseAgent):
    name = "echo"

    async def run(self, query: str, context: dict) -> str:
        return f"echo:{query}"


class FailAgent(BaseAgent):
    name = "fail"

    async def run(self, query: str, context: dict) -> str:
        raise RuntimeError("deliberate failure")


@pytest.fixture
def orchestrator() -> Orchestrator:
    orch = Orchestrator.__new__(Orchestrator)
    orch._agents = {}
    orch.register(EchoAgent())
    orch.register(FailAgent())
    return orch


@pytest.mark.asyncio
async def test_echo_agent(orchestrator: Orchestrator) -> None:
    result = await orchestrator.run("echo", "hello", {})
    assert result == "echo:hello"


@pytest.mark.asyncio
async def test_unknown_agent_raises_key_error(orchestrator: Orchestrator) -> None:
    with pytest.raises(KeyError):
        await orchestrator.run("nonexistent", "query", {})


@pytest.mark.asyncio
async def test_failing_agent_propagates_error(orchestrator: Orchestrator) -> None:
    with pytest.raises(RuntimeError, match="deliberate failure"):
        await orchestrator.run("fail", "query", {})


def test_register_overrides_existing(orchestrator: Orchestrator) -> None:
    class NewEcho(BaseAgent):
        name = "echo"

        async def run(self, query: str, context: dict) -> str:
            return f"new:{query}"

    orchestrator.register(NewEcho())
    assert orchestrator._agents["echo"].__class__.__name__ == "NewEcho"
