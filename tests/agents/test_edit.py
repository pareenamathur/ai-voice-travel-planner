"""Phase 6 — Edit Agent unit tests."""

from __future__ import annotations

from typing import Any

import pytest
from src.agents.edit.agent import EditAgent
from src.agents.edit.intent import parse_edit_intent
from src.mcp_servers.itinerary_builder.service import ItineraryBuilderService
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway, PermissionDeniedError
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole, TaskMessage, TaskType

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
def itinerary_service() -> ItineraryBuilderService:
    return ItineraryBuilderService()


@pytest.fixture
async def base_itinerary(itinerary_service: ItineraryBuilderService) -> dict[str, Any]:
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
    return gw


@pytest.fixture
def edit_agent(gateway: MCPGateway, obs: Observability) -> EditAgent:
    return EditAgent(llm=LLMAdapter(), gateway=gateway, observability=obs)


@pytest.mark.parametrize(
    ("message", "action", "day"),
    [
        ("Make Day 2 more relaxing", "relax_day", 2),
        ("Replace museums with shopping on day 1", "replace_category", 1),
        ("Add a café stop", "add_cafe", None),
        ("Add more adventure", "add_adventure", None),
        ("Remove Albert Hall Museum", "remove_location", None),
        ("Change lunch recommendation", "change_lunch", None),
    ],
)
def test_edit_scope_parser(message: str, action: str, day: int | None):
    parsed = parse_edit_intent(message)
    assert parsed is not None
    assert parsed.action == action
    if day is not None:
        assert parsed.day_number == day


@pytest.mark.asyncio
async def test_edit_agent_uses_gateway_rebuild_day(
    edit_agent: EditAgent,
    gateway: MCPGateway,
    base_itinerary: dict[str, Any],
):
    task = TaskMessage(
        task_type=TaskType.EDIT,
        session_id="sess-edit-1",
        payload={
            "edit_intent": "Make Day 2 more relaxing",
            "itinerary": base_itinerary,
            "before_snapshot": base_itinerary,
            "city": "Jaipur",
        },
        correlation_id="corr-edit-1",
    )

    artifact = await edit_agent.run(task)

    assert artifact.edit_scope.day == 2
    assert artifact.itinerary["traveler_constraints"]["pace"] == "relaxed"
    assert gateway.list_tools() == ["rebuild_day"]


@pytest.mark.asyncio
async def test_edit_preserves_unchanged_days_byte_identical(
    edit_agent: EditAgent,
    base_itinerary: dict[str, Any],
):
    day_one_before = base_itinerary["days"][0]
    task = TaskMessage(
        task_type=TaskType.EDIT,
        session_id="sess-edit-2",
        payload={
            "edit_intent": "Make Day 2 more relaxing",
            "itinerary": base_itinerary,
            "before_snapshot": base_itinerary,
            "city": "Jaipur",
        },
        correlation_id="corr-edit-2",
    )

    artifact = await edit_agent.run(task)

    assert artifact.itinerary["days"][0] == day_one_before
    assert artifact.before_snapshot == base_itinerary


@pytest.mark.asyncio
async def test_edit_agent_returns_edit_artifact_not_user_response(edit_agent: EditAgent, base_itinerary):
    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-3",
            payload={
                "edit_intent": "Change lunch recommendation",
                "itinerary": base_itinerary,
                "before_snapshot": base_itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-3",
        )
    )

    assert hasattr(artifact, "edit_scope")
    assert hasattr(artifact, "before_snapshot")
    assert artifact.correlation_id == "corr-edit-3"


@pytest.mark.asyncio
async def test_planning_denied_rebuild_day(gateway: MCPGateway, base_itinerary: dict[str, Any]):
    with pytest.raises(PermissionDeniedError):
        await gateway.invoke(
            AgentRole.PLANNING,
            "rebuild_day",
            {"itinerary": base_itinerary, "day_number": 1},
        )
