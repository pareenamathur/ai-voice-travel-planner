"""Phase 6 — Edit and Knowledge orchestration integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from src.agents.edit.agent import EditAgent
from src.agents.knowledge.agent import KnowledgeAgent
from src.agents.planning.agent import PlanningAgent
from src.agents.review.agent import ReviewAgent
from src.agents.supervisor.agent import SupervisorAgent
from src.mcp_servers.itinerary_builder.service import ItineraryBuilderService
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.shared.messages.types import (
    AgentResult,
    EditArtifact,
    EditScope,
    EvalReport,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
    TaskMessage,
    TaskType,
)

CITY_PALACE = {
    "osm_id": "node/1",
    "name": "City Palace",
    "lat": 26.9855,
    "lon": 75.8513,
    "category": "culture",
}
HAWA_MAHAL = {
    "osm_id": "node/2",
    "name": "Hawa Mahal",
    "lat": 26.9239,
    "lon": 75.8267,
    "category": "culture",
}
JANTAR_MANTAR = {
    "osm_id": "node/3",
    "name": "Jantar Mantar",
    "lat": 26.9248,
    "lon": 75.8246,
    "category": "culture",
}
ALBERT_HALL = {
    "osm_id": "node/4",
    "name": "Albert Hall Museum",
    "lat": 26.9115,
    "lon": 75.8195,
    "category": "culture",
}


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def sessions() -> SessionManager:
    return SessionManager()


@pytest.fixture
def itinerary_service() -> ItineraryBuilderService:
    return ItineraryBuilderService()


@pytest.fixture
async def approved_itinerary(itinerary_service: ItineraryBuilderService) -> dict[str, Any]:
    built = await itinerary_service.build_itinerary(
        city="Jaipur",
        pois=[CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR, ALBERT_HALL],
        total_days=2,
        traveler_constraints={"pace": "moderate"},
    )
    return dict(built["itinerary"])


@pytest.fixture
def gateway(obs: Observability, itinerary_service: ItineraryBuilderService) -> MCPGateway:
    gw = MCPGateway(observability=obs)
    gw.register("rebuild_day", itinerary_service.rebuild_day)

    async def _retrieve_guidance(**kwargs: Any) -> dict[str, Any]:
        return {
            "source": "rag",
            "chunks": [
                {
                    "chunk_id": "jaipur:wikivoyage::see::0001",
                    "text": "Amber Fort opens early for fewer crowds.",
                    "section": "See",
                    "citation_id": "jaipur:wikivoyage#see#0001",
                    "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
                    "score": 0.9,
                    "metadata": {},
                }
            ],
            "citations": [
                {
                    "citation_id": "jaipur:wikivoyage#see#0001",
                    "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
                    "section": "See",
                    "document_id": "jaipur:wikivoyage",
                    "score": 0.9,
                }
            ],
        }

    gw.register("retrieve_guidance", _retrieve_guidance)
    return gw


def _supervisor_with_real_edit_knowledge(
    sessions: SessionManager,
    gateway: MCPGateway,
    obs: Observability,
    *,
    planning: PlanningAgent | None = None,
    review: ReviewAgent | None = None,
) -> SupervisorAgent:
    return SupervisorAgent(
        llm=LLMAdapter(),
        gateway=gateway,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review or ReviewAgent(LLMAdapter(), gateway, obs),
        edit=EditAgent(LLMAdapter(), gateway, obs),
        knowledge=KnowledgeAgent(LLMAdapter(), gateway, obs),
    )


@pytest.mark.asyncio
async def test_edit_workflow_edit_review_supervisor(
    sessions: SessionManager,
    gateway: MCPGateway,
    obs: Observability,
    approved_itinerary: dict[str, Any],
):
    review = ReviewAgent(LLMAdapter(), gateway, obs)
    supervisor = _supervisor_with_real_edit_knowledge(sessions, gateway, obs, review=review)

    session = sessions.create()
    sessions.set_itinerary(session.session_id, approved_itinerary)
    sessions.set_itinerary_approved(session.session_id, True)

    day_one_before = approved_itinerary["days"][0]
    result = await supervisor.handle_message(
        session.session_id,
        "Make Day 2 more relaxing",
        correlation_id="corr-phase6-edit",
    )

    assert result["intent"] == TaskType.EDIT.value
    assert result["review_verdict"] is not None
    assert result["review_verdict"]["status"] == ReviewStatus.PASS.value
    assert "updated for Day 2" in result["response"]
    assert sessions.read(session.session_id).itinerary_approved is True
    assert sessions.read(session.session_id).itinerary["days"][0] == day_one_before
    assert sessions.read(session.session_id).itinerary["traveler_constraints"]["pace"] == "relaxed"

    spans = obs.get_spans("corr-phase6-edit")
    events = [span.get("event") for span in spans]
    assert "supervisor_dispatch_edit" in events
    assert "review_completed" in events
    assert "user_response_sent" in events


@pytest.mark.asyncio
async def test_explain_workflow_bypasses_review(
    sessions: SessionManager,
    gateway: MCPGateway,
    obs: Observability,
    approved_itinerary: dict[str, Any],
):
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock()
    review.review_edit = AsyncMock()

    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock()

    supervisor = _supervisor_with_real_edit_knowledge(
        sessions,
        gateway,
        obs,
        planning=planning,
        review=review,
    )

    session = sessions.create()
    sessions.set_itinerary(session.session_id, approved_itinerary)
    sessions.set_itinerary_approved(session.session_id, True)

    result = await supervisor.handle_message(
        session.session_id,
        "Tell me more about Amber Fort",
        correlation_id="corr-phase6-explain",
    )

    assert result["intent"] == TaskType.EXPLAIN.value
    assert result["review_verdict"] is None
    assert "Amber Fort" in result["response"]
    review.run.assert_not_called()
    review.review_edit.assert_not_called()
    planning.run.assert_not_called()

    session_data = sessions.read(session.session_id)
    assert session_data.rag_citations
    assert session_data.rag_citations[0]["citation_id"] == "jaipur:wikivoyage#see#0001"

    spans = obs.get_spans("corr-phase6-explain")
    events = [span.get("event") for span in spans]
    assert "supervisor_dispatch_knowledge" in events
    assert "review_started" not in events


@pytest.mark.asyncio
async def test_edit_artifact_not_returned_directly_to_user(
    sessions: SessionManager,
    gateway: MCPGateway,
    obs: Observability,
    approved_itinerary: dict[str, Any],
):
    supervisor = _supervisor_with_real_edit_knowledge(sessions, gateway, obs)
    session = sessions.create()
    sessions.set_itinerary(session.session_id, approved_itinerary)
    sessions.set_itinerary_approved(session.session_id, True)

    result = await supervisor.handle_message(
        session.session_id,
        "Change lunch recommendation",
        correlation_id="corr-phase6-no-shortcut",
    )

    assert result["intent"] == TaskType.EDIT.value
    assert isinstance(result["response"], str)
    assert "edit_scope" not in result["response"]
    assert result["task_message"]["task_type"] == TaskType.EDIT.value


@pytest.mark.asyncio
async def test_knowledge_agent_result_shape_for_supervisor(gateway: MCPGateway, obs: Observability):
    knowledge = KnowledgeAgent(LLMAdapter(), gateway, obs)
    result = await knowledge.run(
        TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id="s",
            payload={"question": "Why?", "city": "Jaipur", "itinerary": {"city": "Jaipur", "days": []}},
            correlation_id="c",
        )
    )
    assert isinstance(result, AgentResult)
