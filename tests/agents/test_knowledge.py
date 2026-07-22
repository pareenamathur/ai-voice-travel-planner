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

    async def _search_pois(**kwargs: Any) -> dict[str, Any]:
        return {
            "pois": [
                {
                    "osm_id": "node/food-1",
                    "name": "LMB Hotel",
                    "lat": 26.9,
                    "lon": 75.8,
                    "category": "food",
                },
                {
                    "osm_id": "node/food-2",
                    "name": "Peacock Rooftop",
                    "lat": 26.91,
                    "lon": 75.81,
                    "category": "food",
                },
            ],
            "source": "test",
            "live_poi_lookup": True,
        }

    gw.register("retrieve_guidance", _retrieve_guidance)
    gw.register("search_pois", _search_pois)
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

    assert "Amber Fort" in result.payload["answer"]
    assert "Day 1" in result.payload["answer"]


@pytest.mark.asyncio
async def test_knowledge_recommend_uses_search_pois(knowledge: KnowledgeAgent, obs: Observability):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.RECOMMEND,
            session_id="sess-k-4",
            payload={
                "question": "Suggest food places in Jaipur",
                "city": "Jaipur",
                "interests": ["food"],
            },
            correlation_id="corr-k-4",
        )
    )

    assert "LMB Hotel" in result.payload["answer"]
    spans = obs.get_spans("corr-k-4")
    tools = [span.get("tool") for span in spans if span.get("event") == "tool_call_start"]
    assert "search_pois" in tools
    assert "retrieve_guidance" in tools


@pytest.mark.asyncio
async def test_why_choose_uses_itinerary_context(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-5",
            payload={
                "question": "Why did you choose City Palace?",
                "city": "Jaipur",
                "itinerary": {
                    "city": "Jaipur",
                    "days": [
                        {
                            "day_number": 1,
                            "activities": [
                                {"title": "City Palace", "category": "culture"},
                                {"title": "Hawa Mahal", "category": "culture"},
                            ],
                        }
                    ],
                },
                "poi_registry": {},
                "trip_constraints": {"interests": ["culture"], "pace": "relaxed"},
            },
            correlation_id="corr-k-5",
        )
    )

    assert "Day 1" in result.payload["answer"]
    assert "City Palace" in result.payload["answer"]
    assert "culture" in result.payload["answer"].lower() or "interests" in result.payload["answer"].lower()
    assert "selected" in result.payload["answer"].lower() or "I planned" in result.payload["answer"]
    assert "What to know about the place:" in result.payload["answer"]


@pytest.mark.asyncio
async def test_feasibility_uses_eval_report(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-feas",
            payload={
                "question": "Is Day 2 too packed?",
                "city": "Jaipur",
                "itinerary": {
                    "city": "Jaipur",
                    "days": [
                        {
                            "day_number": 1,
                            "activities": [{"title": "City Palace", "duration_minutes": 90}],
                            "travel_segments": [],
                        },
                        {
                            "day_number": 2,
                            "activities": [
                                {"title": "Amber Fort", "duration_minutes": 120},
                                {"title": "Jal Mahal", "duration_minutes": 60},
                                {"title": "Hawa Mahal", "duration_minutes": 60},
                                {"title": "Albert Hall", "duration_minutes": 90},
                                {"title": "Johari Bazaar", "duration_minutes": 60},
                            ],
                            "travel_segments": [{"travel_minutes": 40}],
                        },
                    ],
                    "traveler_constraints": {"pace": "relaxed"},
                },
                "trip_constraints": {"pace": "relaxed"},
                "eval_report": {
                    "entries": [
                        {
                            "name": "feasibility",
                            "passed": False,
                            "reasons": ["day 2: 5 activities exceeds 5 allowed for 'relaxed' pace"],
                        }
                    ]
                },
            },
            correlation_id="corr-k-feas",
        )
    )

    answer = result.payload["answer"]
    assert "Day 2" in answer
    assert "evaluation" in answer.lower() or "packing" in answer.lower()
    assert "generic advice" not in answer.lower()


@pytest.mark.asyncio
async def test_rain_answer_uses_itinerary_indoor_outdoor(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-rain",
            payload={
                "question": "What if it rains?",
                "city": "Jaipur",
                "itinerary": {
                    "city": "Jaipur",
                    "days": [
                        {
                            "day_number": 1,
                            "activities": [
                                {"title": "Amber Fort", "category": "landmark"},
                                {"title": "Albert Hall Museum", "category": "culture"},
                            ],
                        }
                    ],
                },
                "trip_constraints": {"pace": "moderate"},
            },
            correlation_id="corr-k-rain",
        )
    )

    answer = result.payload["answer"]
    assert "Amber Fort" in answer
    assert "Albert Hall" in answer or "indoor" in answer.lower()
    assert "umbrella" not in answer.lower() or "adapt" in answer.lower()


@pytest.mark.asyncio
async def test_kid_friendly_answer_avoids_itinerary_dump(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-kids",
            payload={
                "question": "Is it kid friendly?",
                "city": "Jaipur",
                "itinerary": SAMPLE_ITINERARY,
                "trip_constraints": {"pace": "relaxed"},
            },
            correlation_id="corr-k-kids",
        )
    )
    answer = result.payload["answer"]
    assert "kid" in answer.lower() or "family" in answer.lower()
    assert "on your Day" not in answer


@pytest.mark.asyncio
async def test_packing_answer_is_focused(knowledge: KnowledgeAgent):
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="sess-k-pack",
            payload={
                "question": "What should I pack?",
                "city": "Jaipur",
                "itinerary": SAMPLE_ITINERARY,
                "trip_constraints": {"pace": "moderate"},
            },
            correlation_id="corr-k-pack",
        )
    )
    answer = result.payload["answer"]
    assert "pack" in answer.lower() or "bring" in answer.lower() or "shoes" in answer.lower()
    assert "Day 1" not in answer
