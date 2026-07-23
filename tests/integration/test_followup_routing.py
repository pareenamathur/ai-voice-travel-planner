"""Regression: after planning, follow-up questions must not re-enter confirmation."""

from __future__ import annotations

from typing import Any

import pytest

from src.agents.registry import AgentRegistry
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.shared.messages.types import TaskType
from tests.integration.test_phase4_orchestration import (
    SAMPLE_ITINERARY,
    SAMPLE_POIS,
    RecordingGateway,
)


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def sessions() -> SessionManager:
    return SessionManager()


@pytest.fixture
def gateway(obs: Observability) -> RecordingGateway:
    return RecordingGateway(observability=obs)


@pytest.fixture
def registry(
    sessions: SessionManager,
    gateway: RecordingGateway,
    obs: Observability,
) -> AgentRegistry:
    return AgentRegistry(
        session_manager=sessions,
        llm=LLMAdapter(),
        gateway=gateway,
        observability=obs,
    )


async def _plan_jaipur(registry: AgentRegistry) -> dict[str, Any]:
    supervisor = registry.supervisor
    confirm = await supervisor.handle_message(
        None,
        "Plan a 3 day Jaipur trip",
        correlation_id="corr-followup-confirm",
    )
    assert confirm["intent"] == TaskType.CONFIRM.value
    return await supervisor.handle_message(
        confirm["session_id"],
        "yes",
        correlation_id="corr-followup-plan",
    )


@pytest.mark.asyncio
async def test_doable_after_plan_is_explain_not_confirm(registry: AgentRegistry):
    planned = await _plan_jaipur(registry)
    assert planned["intent"] == TaskType.PLAN.value
    assert planned["itinerary_approved"] is True

    follow = await registry.supervisor.handle_message(
        planned["session_id"],
        "Is this plan doable?",
        correlation_id="corr-followup-doable",
    )
    assert follow["intent"] == TaskType.EXPLAIN.value
    assert "Would you like me to generate" not in follow["response"]
    assert follow["itinerary"] is None


@pytest.mark.asyncio
async def test_rain_before_plan_is_explain_when_draft_exists(
    registry: AgentRegistry,
    sessions: SessionManager,
):
    session = sessions.create()
    sessions.update_constraints(session.session_id, {"city": "Jaipur", "days": 3})
    sessions.set_itinerary(session.session_id, dict(SAMPLE_ITINERARY))
    sessions.set_itinerary_approved(session.session_id, True)

    rain = await registry.supervisor.handle_message(
        session.session_id,
        "What if it rains?",
        correlation_id="corr-rain-draft",
    )
    assert rain["intent"] == TaskType.EXPLAIN.value
    assert "Would you like me to generate" not in rain["response"]


@pytest.mark.asyncio
async def test_why_amber_fort_after_plan(registry: AgentRegistry, gateway: RecordingGateway):
    planned = await _plan_jaipur(registry)
    calls_before = len(gateway.calls)

    why = await registry.supervisor.handle_message(
        planned["session_id"],
        "Why did you recommend Amber Fort?",
        correlation_id="corr-followup-why",
    )
    assert why["intent"] == TaskType.EXPLAIN.value
    assert "Would you like me to generate" not in why["response"]
    tool_names = [name for name, _ in gateway.calls[calls_before:]]
    assert "search_pois" not in tool_names
    assert "build_itinerary" not in tool_names


@pytest.mark.asyncio
async def test_plan_uses_live_pois_when_overpass_returns_data(gateway: RecordingGateway):
    async def _live_search(**kwargs: Any) -> dict[str, Any]:
        return {
            "source": "osm",
            "pois": list(SAMPLE_POIS),
            "live_poi_lookup": True,
        }

    gateway.register("search_pois", _live_search)

    registry = AgentRegistry(
        session_manager=SessionManager(),
        llm=LLMAdapter(),
        gateway=gateway,
        observability=Observability(),
    )
    planned = await _plan_jaipur(registry)
    itinerary = planned["itinerary"] or {}
    metadata = itinerary.get("metadata") or {}
    assert metadata.get("live_poi_lookup") is True
    assert "temporarily unavailable" not in planned["response"].lower()
