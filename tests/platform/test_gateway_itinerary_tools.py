"""Gateway registration tests for Itinerary Builder MCP tools (Phase 3 Task 4)."""

from __future__ import annotations

import pytest
from src.api.deps import get_registry, reset_registry
from src.platform.mcp_gateway.gateway import PermissionDeniedError
from src.shared.itinerary import Itinerary
from src.shared.messages.types import AgentRole

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


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry()
    yield
    reset_registry()


def test_itinerary_tools_registered_in_gateway():
    registry = get_registry()
    tools = registry.gateway.list_tools()

    assert "build_itinerary" in tools
    assert "rebuild_day" in tools
    assert registry.gateway.is_permitted(AgentRole.PLANNING, "build_itinerary") is True
    assert "build_itinerary" in registry.gateway.list_tools_for_role(AgentRole.PLANNING)
    assert "rebuild_day" in registry.gateway.list_tools_for_role(AgentRole.EDIT)


@pytest.mark.asyncio
async def test_planning_agent_can_invoke_build_itinerary():
    registry = get_registry()
    result = await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        {
            "city": "Jaipur",
            "pois": [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR],
            "total_days": 2,
            "traveler_constraints": {"pace": "moderate"},
        },
    )

    assert result["source"] == "itinerary_builder"
    itinerary = Itinerary.model_validate(result["itinerary"])
    assert itinerary.city == "Jaipur"
    assert itinerary.total_days == 2


@pytest.mark.asyncio
async def test_edit_agent_can_invoke_rebuild_day():
    registry = get_registry()
    built = await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        {
            "city": "Jaipur",
            "pois": [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR],
            "total_days": 1,
        },
    )

    result = await registry.gateway.invoke(
        AgentRole.EDIT,
        "rebuild_day",
        {
            "itinerary": built["itinerary"],
            "day_number": 1,
            "traveler_constraints": {"pace": "relaxed"},
        },
    )

    assert result["source"] == "itinerary_builder"
    itinerary = Itinerary.model_validate(result["itinerary"])
    assert itinerary.traveler_constraints.pace == "relaxed"


@pytest.mark.asyncio
async def test_supervisor_denied_build_itinerary():
    registry = get_registry()
    with pytest.raises(PermissionDeniedError) as exc_info:
        await registry.gateway.invoke(
            AgentRole.SUPERVISOR,
            "build_itinerary",
            {
                "city": "Jaipur",
                "pois": [CITY_PALACE],
                "total_days": 1,
            },
        )

    assert exc_info.value.role == AgentRole.SUPERVISOR
    assert exc_info.value.tool_name == "build_itinerary"


@pytest.mark.asyncio
async def test_supervisor_denied_rebuild_day():
    registry = get_registry()
    with pytest.raises(PermissionDeniedError) as exc_info:
        await registry.gateway.invoke(
            AgentRole.SUPERVISOR,
            "rebuild_day",
            {"itinerary": {"city": "Jaipur", "total_days": 1, "days": []}, "day_number": 1},
        )

    assert exc_info.value.role == AgentRole.SUPERVISOR
    assert exc_info.value.tool_name == "rebuild_day"


@pytest.mark.asyncio
async def test_knowledge_agent_denied_build_itinerary():
    registry = get_registry()
    with pytest.raises(PermissionDeniedError) as exc_info:
        await registry.gateway.invoke(
            AgentRole.KNOWLEDGE,
            "build_itinerary",
            {
                "city": "Jaipur",
                "pois": [CITY_PALACE],
                "total_days": 1,
            },
        )

    assert exc_info.value.role == AgentRole.KNOWLEDGE
    assert exc_info.value.tool_name == "build_itinerary"


@pytest.mark.asyncio
async def test_knowledge_agent_denied_rebuild_day():
    registry = get_registry()
    with pytest.raises(PermissionDeniedError) as exc_info:
        await registry.gateway.invoke(
            AgentRole.KNOWLEDGE,
            "rebuild_day",
            {"itinerary": {"city": "Jaipur", "total_days": 1, "days": []}, "day_number": 1},
        )

    assert exc_info.value.role == AgentRole.KNOWLEDGE
    assert exc_info.value.tool_name == "rebuild_day"


@pytest.mark.asyncio
async def test_gateway_emits_observability_spans_for_itinerary_tools():
    registry = get_registry()
    corr_id = "corr-itinerary-42"

    await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        {
            "city": "Jaipur",
            "pois": [CITY_PALACE, HAWA_MAHAL],
            "total_days": 1,
        },
        correlation_id=corr_id,
    )

    spans = registry.observability.get_spans(corr_id)
    events = [span.get("event") for span in spans]
    tools = [span.get("tool") for span in spans]

    assert "tool_call_start" in events
    assert "tool_call_complete" in events
    assert "build_itinerary" in tools
    assert all(span.get("correlation_id") == corr_id for span in spans)


def test_retrieve_guidance_registered_in_gateway():
    registry = get_registry()
    tools = registry.gateway.list_tools()

    assert "retrieve_guidance" in tools
    assert registry.gateway.is_permitted(AgentRole.KNOWLEDGE, "retrieve_guidance") is True
    assert "retrieve_guidance" in registry.gateway.list_tools_for_role(AgentRole.KNOWLEDGE)


@pytest.mark.asyncio
async def test_knowledge_agent_can_invoke_retrieve_guidance():
    registry = get_registry()
    result = await registry.gateway.invoke(
        AgentRole.KNOWLEDGE,
        "retrieve_guidance",
        {"query": "Amber Fort opening hours", "city": "Jaipur", "top_k": 3},
    )

    assert result["source"] == "rag"
    assert "chunks" in result
    assert "citations" in result


@pytest.mark.asyncio
async def test_edit_agent_denied_retrieve_guidance():
    registry = get_registry()
    with pytest.raises(PermissionDeniedError) as exc_info:
        await registry.gateway.invoke(
            AgentRole.EDIT,
            "retrieve_guidance",
            {"query": "Amber Fort", "city": "Jaipur"},
        )

    assert exc_info.value.role == AgentRole.EDIT
    assert exc_info.value.tool_name == "retrieve_guidance"
