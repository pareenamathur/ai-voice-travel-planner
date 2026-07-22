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
        ("Add one famous local food place", "add_food", None),
        ("Add more adventure", "add_adventure", None),
        ("Remove Albert Hall Museum", "remove_location", None),
        ("Replace Amber Fort", "replace_location", None),
        ("Move Jal Mahal to Day 3", "move_location", 3),
        ("Reduce travel time", "reduce_travel", None),
        ("Swap the Day 1 evening plan to something indoors", "make_indoors", 1),
        ("Change lunch recommendation", "change_lunch", None),
        ("Make Day 3 a food tour", "food_tour", 3),
        ("Replace Day 2 with Udaipur", "replace_day_city", 2),
        ("Make the itinerary more luxurious", "luxury_pace", None),
        ("Spend more time outdoors", "outdoors_day", None),
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


@pytest.mark.asyncio
async def test_relax_day_drops_a_stop_and_preserves_other_days(
    edit_agent: EditAgent,
    base_itinerary: dict[str, Any],
):
    day_one_before = base_itinerary["days"][0]
    day_two_sights_before = len(
        [a for a in base_itinerary["days"][1]["activities"] if a.get("poi_id")]
    )
    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-relax",
            payload={
                "edit_intent": "Make Day 2 more relaxed.",
                "itinerary": base_itinerary,
                "before_snapshot": base_itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-relax",
        )
    )

    assert artifact.itinerary["days"][0] == day_one_before
    assert artifact.itinerary["traveler_constraints"]["pace"] == "relaxed"
    day_two_sights_after = len(
        [a for a in artifact.itinerary["days"][1]["activities"] if a.get("poi_id")]
    )
    assert day_two_sights_after < day_two_sights_before


@pytest.mark.asyncio
async def test_add_food_inserts_one_meal_without_replacing_sightseeing(
    edit_agent: EditAgent,
    base_itinerary: dict[str, Any],
):
    before_sights = [
        a["title"] for a in base_itinerary["days"][0]["activities"] if a.get("poi_id")
    ]
    day_two_before = base_itinerary["days"][1]
    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-food",
            payload={
                "edit_intent": "Add one famous local food place",
                "itinerary": base_itinerary,
                "before_snapshot": base_itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-food",
        )
    )

    after_sights = [
        a["title"] for a in artifact.itinerary["days"][0]["activities"] if a.get("poi_id")
    ]
    assert all(title in after_sights for title in before_sights)
    assert len(after_sights) == len(before_sights) + 1
    assert any(
        a.get("category") == "food" for a in artifact.itinerary["days"][0]["activities"]
    )
    assert artifact.itinerary["days"][1] == day_two_before


@pytest.mark.asyncio
async def test_reduce_travel_reorders_existing_pois(
    edit_agent: EditAgent,
    itinerary_service: ItineraryBuilderService,
):
    built = await itinerary_service.build_itinerary(
        city="Jaipur",
        pois=[
            {**CITY_PALACE, "lat": 26.99, "lon": 75.85},
            {**HAWA_MAHAL, "lat": 26.92, "lon": 75.82},
            {**JANTAR_MANTAR, "lat": 26.925, "lon": 75.825},
            {**ALBERT_HALL, "lat": 26.91, "lon": 75.81},
        ],
        total_days=1,
        traveler_constraints={"pace": "moderate"},
    )
    itinerary = dict(built["itinerary"])
    before_ids = [
        a["poi_id"] for a in itinerary["days"][0]["activities"] if a.get("poi_id")
    ]

    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-travel",
            payload={
                "edit_intent": "Reduce travel time",
                "itinerary": itinerary,
                "before_snapshot": itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-travel",
        )
    )

    after_ids = [
        a["poi_id"] for a in artifact.itinerary["days"][0]["activities"] if a.get("poi_id")
    ]
    assert set(after_ids) == set(before_ids)
    assert len(after_ids) == len(before_ids)


@pytest.mark.asyncio
async def test_replace_named_poi_only_affects_its_day(
    edit_agent: EditAgent,
    itinerary_service: ItineraryBuilderService,
):
    built = await itinerary_service.build_itinerary(
        city="Jaipur",
        pois=[
            CITY_PALACE,
            HAWA_MAHAL,
            {**JANTAR_MANTAR, "name": "Amber Fort", "osm_id": "node/amber", "category": "landmark"},
            ALBERT_HALL,
        ],
        total_days=2,
        traveler_constraints={"pace": "moderate"},
    )
    itinerary = dict(built["itinerary"])
    amber_day = next(
        d["day_number"]
        for d in itinerary["days"]
        for a in d["activities"]
        if "Amber" in a["title"]
    )
    other_day = 1 if amber_day == 2 else 2
    other_before = next(d for d in itinerary["days"] if d["day_number"] == other_day)

    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-replace",
            payload={
                "edit_intent": "Replace Amber Fort",
                "itinerary": itinerary,
                "before_snapshot": itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-replace",
        )
    )

    titles = [
        a["title"]
        for d in artifact.itinerary["days"]
        for a in d["activities"]
    ]
    assert not any("Amber Fort" in t for t in titles)
    assert next(d for d in artifact.itinerary["days"] if d["day_number"] == other_day) == other_before


@pytest.mark.asyncio
async def test_move_poi_between_days_preserves_untouched_day(
    edit_agent: EditAgent,
    itinerary_service: ItineraryBuilderService,
):
    built = await itinerary_service.build_itinerary(
        city="Jaipur",
        pois=[
            CITY_PALACE,
            HAWA_MAHAL,
            JANTAR_MANTAR,
            {**ALBERT_HALL, "name": "Jal Mahal", "osm_id": "node/jal", "category": "landmark"},
        ],
        total_days=3,
        traveler_constraints={"pace": "moderate"},
    )
    itinerary = dict(built["itinerary"])
    source_day = next(
        d["day_number"]
        for d in itinerary["days"]
        for a in d["activities"]
        if "Jal Mahal" in a["title"]
    )
    dest_day = 1 if source_day != 1 else 2
    untouched = next(
        d["day_number"] for d in itinerary["days"] if d["day_number"] not in {source_day, dest_day}
    )
    untouched_before = next(d for d in itinerary["days"] if d["day_number"] == untouched)

    artifact = await edit_agent.run(
        TaskMessage(
            task_type=TaskType.EDIT,
            session_id="sess-edit-move",
            payload={
                "edit_intent": f"Move Jal Mahal to Day {dest_day}",
                "itinerary": itinerary,
                "before_snapshot": itinerary,
                "city": "Jaipur",
            },
            correlation_id="corr-edit-move",
        )
    )

    dest_titles = [
        a["title"]
        for d in artifact.itinerary["days"]
        if d["day_number"] == dest_day
        for a in d["activities"]
    ]
    source_titles = [
        a["title"]
        for d in artifact.itinerary["days"]
        if d["day_number"] == source_day
        for a in d["activities"]
    ]
    assert any("Jal Mahal" in t for t in dest_titles)
    assert not any("Jal Mahal" in t for t in source_titles)
    assert next(d for d in artifact.itinerary["days"] if d["day_number"] == untouched) == untouched_before
