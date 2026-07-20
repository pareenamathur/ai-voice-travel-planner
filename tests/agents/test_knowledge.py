"""Phase 6 — Knowledge Agent unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from src.agents.knowledge.agent import KnowledgeAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway, PermissionDeniedError
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole, TaskMessage, TaskType

SAMPLE_ITINERARY = {
    "city": "Jaipur",
    "total_days": 1,
    "days": [
        {
            "day_number": 1,
            "activities": [{"title": "Amber Fort", "poi_id": "node/6", "category": "sightseeing"}],
            "travel_segments": [],
        }
    ],
}

GUIDANCE_PAYLOAD = {
    "source": "rag",
    "chunks": [
        {
            "chunk_id": "jaipur:wikivoyage::see::0001",
            "text": "Amber Fort is best visited in the early morning.",
            "section": "See",
            "citation_id": "jaipur:wikivoyage#see#0001",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            "score": 0.91,
            "metadata": {},
        }
    ],
    "citations": [
        {
            "citation_id": "jaipur:wikivoyage#see#0001",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            "section": "See",
            "document_id": "jaipur:wikivoyage",
            "score": 0.91,
        }
    ],
}


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def gateway(obs: Observability) -> MCPGateway:
    gw = MCPGateway(observability=obs)

    async def _retrieve_guidance(**kwargs: Any) -> dict[str, Any]:
        return GUIDANCE_PAYLOAD

    gw.register("retrieve_guidance", _retrieve_guidance)
    return gw


@pytest.fixture
def knowledge(gateway: MCPGateway, obs: Observability) -> KnowledgeAgent:
    return KnowledgeAgent(llm=LLMAdapter(), gateway=gateway, observability=obs)


@pytest.mark.asyncio
async def test_knowledge_returns_agent_result_with_citations(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-1",
            payload={
                "question": "Tell me more about Amber Fort",
                "city": "Jaipur",
                "itinerary": SAMPLE_ITINERARY,
                "poi_registry": {"node/6": {"name": "Amber Fort", "category": "sightseeing"}},
            },
            correlation_id="corr-k-1",
        )
    )

    assert result.status == "ok"
    assert result.citations
    assert result.citations[0]["citation_id"] == "jaipur:wikivoyage#see#0001"
    assert "Amber Fort" in result.payload["answer"]


@pytest.mark.asyncio
async def test_knowledge_uses_gateway_retrieve_guidance_only(
    knowledge: KnowledgeAgent,
    gateway: MCPGateway,
    obs: Observability,
):
    await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-2",
            payload={
                "question": "What is special about Hawa Mahal?",
                "city": "Jaipur",
                "itinerary": SAMPLE_ITINERARY,
            },
            correlation_id="corr-k-2",
        )
    )

    spans = obs.get_spans("corr-k-2")
    tools = [span.get("tool") for span in spans if span.get("event") == "tool_call_start"]
    assert tools == ["retrieve_guidance"]
    assert gateway.is_permitted(AgentRole.KNOWLEDGE, "retrieve_guidance") is True


@pytest.mark.asyncio
async def test_planning_denied_retrieve_guidance(gateway: MCPGateway):
    with pytest.raises(PermissionDeniedError):
        await gateway.invoke(
            AgentRole.PLANNING,
            "retrieve_guidance",
            {"query": "Amber Fort", "city": "Jaipur"},
        )


@pytest.mark.asyncio
async def test_why_recommend_uses_registry_context(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-3",
            payload={
                "question": "Why did you recommend Amber Fort?",
                "city": "Jaipur",
                "itinerary": SAMPLE_ITINERARY,
                "poi_registry": {"node/6": {"name": "Amber Fort", "category": "sightseeing"}},
            },
            correlation_id="corr-k-3",
        )
    )

    assert "recommended Amber Fort" in result.payload["answer"]
