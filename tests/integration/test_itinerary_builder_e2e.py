"""Phase 3 Task 5 — end-to-end integration tests for Itinerary Builder MCP.

Flow under test:
    Planning (simulated via AgentRole.PLANNING)
        → MCP Gateway
        → build_itinerary / rebuild_day
        → ItineraryBuilderService
        → scheduler
        → canonical Itinerary schema
"""

from __future__ import annotations

from datetime import date

import pytest
from src.api.deps import get_registry, reset_registry
from src.shared.itinerary import Itinerary
from src.shared.messages.types import AgentRole

JAIPUR_POIS = [
    {
        "osm_id": "node/1",
        "name": "City Palace",
        "lat": 26.9855,
        "lon": 75.8513,
        "category": "culture",
    },
    {
        "osm_id": "node/2",
        "name": "Hawa Mahal",
        "lat": 26.9239,
        "lon": 75.8267,
        "category": "culture",
    },
    {
        "osm_id": "node/3",
        "name": "Jantar Mantar",
        "lat": 26.9248,
        "lon": 75.8246,
        "category": "culture",
    },
    {
        "osm_id": "node/4",
        "name": "Albert Hall Museum",
        "lat": 26.9115,
        "lon": 75.8195,
        "category": "culture",
    },
    {
        "osm_id": "node/5",
        "name": "Nahargarh Fort",
        "lat": 26.9376,
        "lon": 75.8155,
        "category": "sightseeing",
    },
    {
        "osm_id": "node/6",
        "name": "Amber Fort",
        "lat": 26.9855,
        "lon": 75.8513,
        "category": "sightseeing",
    },
]


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry()
    yield
    reset_registry()


def _input_poi_ids(pois: list[dict]) -> set[str]:
    return {poi["osm_id"] for poi in pois}


def assert_canonical_itinerary(
    payload: dict,
    *,
    expected_city: str | None = None,
    expected_days: int | None = None,
    input_poi_ids: set[str] | None = None,
) -> Itinerary:
    """Validate gateway payload round-trips through the shared Itinerary model."""
    assert payload.get("source") == "itinerary_builder"
    assert "itinerary" in payload

    itinerary = Itinerary.model_validate(payload["itinerary"])

    assert itinerary.city
    assert itinerary.total_days >= 1
    assert isinstance(itinerary.traveler_constraints.interests, list)
    assert isinstance(itinerary.days, list)
    assert isinstance(itinerary.poi_registry, list)
    assert isinstance(itinerary.citations, list)
    assert isinstance(itinerary.metadata, dict)

    assert len(itinerary.days) == itinerary.total_days
    assert [day.day_number for day in itinerary.days] == list(
        range(1, itinerary.total_days + 1)
    )

    if expected_city is not None:
        assert itinerary.city == expected_city
    if expected_days is not None:
        assert itinerary.total_days == expected_days

    scheduled_poi_ids: set[str] = set()
    for day in itinerary.days:
        for activity in day.activities:
            assert activity.id
            assert activity.title
            if activity.poi_id is not None:
                scheduled_poi_ids.add(activity.poi_id)
        for segment in day.travel_segments:
            assert segment.from_activity_id
            assert segment.to_activity_id
            assert segment.travel_minutes >= 0

    if input_poi_ids is not None:
        assert scheduled_poi_ids.issubset(input_poi_ids)

    registry_ids = {ref.poi_id for ref in itinerary.poi_registry}
    assert scheduled_poi_ids.issubset(registry_ids)

    return itinerary


async def _planning_build(
    registry,
    *,
    city: str = "Jaipur",
    pois: list[dict],
    total_days: int,
    correlation_id: str = "",
    **kwargs,
) -> dict:
    """Simulate the Planning agent invoking ``build_itinerary`` through the Gateway."""
    params = {
        "city": city,
        "pois": pois,
        "total_days": total_days,
        **kwargs,
    }
    return await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        params,
        correlation_id=correlation_id,
    )


async def _edit_rebuild(
    registry,
    *,
    itinerary: dict,
    day_number: int,
    correlation_id: str = "",
    **kwargs,
) -> dict:
    """Simulate the Edit agent invoking ``rebuild_day`` through the Gateway."""
    params = {
        "itinerary": itinerary,
        "day_number": day_number,
        **kwargs,
    }
    return await registry.gateway.invoke(
        AgentRole.EDIT,
        "rebuild_day",
        params,
        correlation_id=correlation_id,
    )


@pytest.mark.asyncio
async def test_e2e_planning_gateway_build_itinerary_two_days():
    registry = get_registry()
    pois = JAIPUR_POIS[:4]

    result = await _planning_build(
        registry,
        pois=pois,
        total_days=2,
        traveler_constraints={"pace": "moderate"},
        start_date="2026-04-01",
    )

    itinerary = assert_canonical_itinerary(
        result,
        expected_city="Jaipur",
        expected_days=2,
        input_poi_ids=_input_poi_ids(pois),
    )
    assert itinerary.start_date == date(2026, 4, 1)
    assert itinerary.metadata.get("scheduler") == "heuristic_v1"
    assert sum(len(day.activities) for day in itinerary.days) >= 1


@pytest.mark.asyncio
async def test_e2e_planning_gateway_build_itinerary_three_days():
    """Deliverable: 3-day sample itinerary via Gateway tool calls."""
    registry = get_registry()

    result = await _planning_build(
        registry,
        pois=JAIPUR_POIS,
        total_days=3,
        traveler_constraints={
            "pace": "relaxed",
            "daily_window_start": "09:00",
            "daily_window_end": "21:00",
        },
        start_date="2026-04-10",
    )

    itinerary = assert_canonical_itinerary(
        result,
        expected_city="Jaipur",
        expected_days=3,
        input_poi_ids=_input_poi_ids(JAIPUR_POIS),
    )
    assert itinerary.start_date == date(2026, 4, 10)
    assert itinerary.traveler_constraints.pace == "relaxed"
    assert itinerary.traveler_constraints.daily_window_start == "09:00"
    assert itinerary.traveler_constraints.daily_window_end == "21:00"


@pytest.mark.asyncio
async def test_e2e_build_itinerary_empty_poi_list():
    registry = get_registry()

    result = await _planning_build(registry, pois=[], total_days=2)

    itinerary = assert_canonical_itinerary(
        result,
        expected_city="Jaipur",
        expected_days=2,
        input_poi_ids=set(),
    )
    assert all(len(day.activities) == 0 for day in itinerary.days)
    assert itinerary.poi_registry == []


@pytest.mark.asyncio
async def test_e2e_build_itinerary_is_deterministic():
    registry = get_registry()
    params = {
        "pois": JAIPUR_POIS[:3],
        "total_days": 2,
        "traveler_constraints": {"pace": "packed"},
    }

    first = await _planning_build(registry, **params)
    second = await _planning_build(registry, **params)

    assert first == second
    assert_canonical_itinerary(first, expected_days=2, input_poi_ids=_input_poi_ids(params["pois"]))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "match"),
    [
        (
            {"city": "  ", "pois": JAIPUR_POIS[:1], "total_days": 1},
            "city is required",
        ),
        (
            {"city": "Jaipur", "pois": JAIPUR_POIS[:1], "total_days": 0},
            "total_days must be at least 1",
        ),
        (
            {
                "city": "Jaipur",
                "pois": [{"name": "Missing coordinates"}],
                "total_days": 1,
            },
            "invalid POI payload",
        ),
        (
            {
                "city": "Jaipur",
                "pois": JAIPUR_POIS[:1],
                "total_days": 1,
                "traveler_constraints": {"party_size": 0},
            },
            "invalid traveler_constraints payload",
        ),
        (
            {
                "city": "Jaipur",
                "pois": JAIPUR_POIS[:1],
                "total_days": 1,
                "start_date": "not-a-date",
            },
            "invalid start_date",
        ),
    ],
)
async def test_e2e_build_itinerary_rejects_invalid_inputs(params, match):
    registry = get_registry()
    with pytest.raises(ValueError, match=match):
        await registry.gateway.invoke(AgentRole.PLANNING, "build_itinerary", params)


@pytest.mark.asyncio
async def test_e2e_rebuild_day_produces_schema_valid_itinerary():
    registry = get_registry()

    built = await _planning_build(
        registry,
        pois=JAIPUR_POIS,
        total_days=3,
        start_date="2026-05-01",
    )
    original = built["itinerary"]
    day_one_before = original["days"][0]
    day_three_before = original["days"][2]

    rebuilt = await _edit_rebuild(
        registry,
        itinerary=original,
        day_number=2,
        pois=[JAIPUR_POIS[1], JAIPUR_POIS[2]],
        traveler_constraints={"pace": "fast"},
    )

    itinerary = assert_canonical_itinerary(
        rebuilt,
        expected_city="Jaipur",
        expected_days=3,
        input_poi_ids=_input_poi_ids(JAIPUR_POIS),
    )
    assert itinerary.traveler_constraints.pace == "fast"
    assert rebuilt["itinerary"]["days"][0] == day_one_before
    assert rebuilt["itinerary"]["days"][2] == day_three_before
    assert rebuilt["itinerary"]["days"][1] != original["days"][1]


@pytest.mark.asyncio
async def test_e2e_full_flow_records_observability_with_correlation_id():
    registry = get_registry()
    correlation_id = "phase3-e2e-turn"

    await _planning_build(
        registry,
        pois=JAIPUR_POIS[:2],
        total_days=1,
        correlation_id=correlation_id,
    )

    spans = registry.observability.get_spans(correlation_id)
    assert spans
    assert spans[0]["event"] == "tool_call_start"
    assert spans[0]["tool"] == "build_itinerary"
    assert spans[-1]["event"] == "tool_call_complete"
    assert all(span.get("correlation_id") == correlation_id for span in spans)
