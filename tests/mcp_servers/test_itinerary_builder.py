"""Phase 3 Task 3 — Itinerary Builder MCP service tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from src.mcp_servers.itinerary_builder.service import ItineraryBuilderService
from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import Itinerary, TravelerConstraints

CITY_PALACE = POI(
    osm_id="node/1",
    name="City Palace",
    lat=26.9855,
    lon=75.8513,
    category="culture",
)
HAWA_MAHAL = POI(
    osm_id="node/2",
    name="Hawa Mahal",
    lat=26.9239,
    lon=75.8267,
    category="culture",
)
JANTAR_MANTAR = POI(
    osm_id="node/3",
    name="Jantar Mantar",
    lat=26.9248,
    lon=75.8246,
    category="culture",
)
ALBERT_HALL = POI(
    osm_id="node/4",
    name="Albert Hall Museum",
    lat=26.9115,
    lon=75.8195,
    category="culture",
)
NAHARGARH = POI(
    osm_id="node/5",
    name="Nahargarh Fort",
    lat=26.9376,
    lon=75.8155,
    category="sightseeing",
)
AMBER_FORT = POI(
    osm_id="node/6",
    name="Amber Fort",
    lat=26.9855,
    lon=75.8513,
    category="sightseeing",
)


def _poi_dict(poi: POI) -> dict:
    return poi.model_dump()


@pytest.fixture
def service() -> ItineraryBuilderService:
    return ItineraryBuilderService()


@pytest.mark.asyncio
async def test_build_itinerary_returns_canonical_schema(service: ItineraryBuilderService):
    result = await service.build_itinerary(
        city="Jaipur",
        pois=[_poi_dict(CITY_PALACE), _poi_dict(HAWA_MAHAL), _poi_dict(JANTAR_MANTAR)],
        total_days=2,
        traveler_constraints={"pace": "moderate"},
        start_date="2026-04-01",
    )

    assert result["source"] == "itinerary_builder"
    itinerary = Itinerary.model_validate(result["itinerary"])
    assert itinerary.city == "Jaipur"
    assert itinerary.total_days == 2
    assert itinerary.start_date == date(2026, 4, 1)
    assert len(itinerary.days) == 2
    assert itinerary.traveler_constraints.pace == "moderate"
    assert itinerary.metadata.get("scheduler") == "heuristic_v1"


@pytest.mark.asyncio
async def test_build_itinerary_is_deterministic(service: ItineraryBuilderService):
    payload = {
        "city": "Jaipur",
        "pois": [_poi_dict(CITY_PALACE), _poi_dict(HAWA_MAHAL)],
        "total_days": 1,
        "traveler_constraints": {"pace": "relaxed"},
    }
    first = await service.build_itinerary(**payload)
    second = await service.build_itinerary(**payload)
    assert first == second


@pytest.mark.asyncio
async def test_build_itinerary_rejects_empty_city(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="city is required"):
        await service.build_itinerary(city="  ", pois=[_poi_dict(CITY_PALACE)], total_days=1)


@pytest.mark.asyncio
async def test_build_itinerary_rejects_invalid_total_days(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="total_days must be at least 1"):
        await service.build_itinerary(city="Jaipur", pois=[_poi_dict(CITY_PALACE)], total_days=0)


@pytest.mark.asyncio
async def test_build_itinerary_rejects_invalid_start_date(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="invalid start_date"):
        await service.build_itinerary(
            city="Jaipur",
            pois=[_poi_dict(CITY_PALACE)],
            total_days=1,
            start_date="not-a-date",
        )


@pytest.mark.asyncio
async def test_build_itinerary_rejects_invalid_poi_payload(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="invalid POI payload"):
        await service.build_itinerary(
            city="Jaipur",
            pois=[{"name": "Missing coordinates"}],
            total_days=1,
        )


@pytest.mark.asyncio
async def test_build_itinerary_rejects_invalid_constraints(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="invalid traveler_constraints payload"):
        await service.build_itinerary(
            city="Jaipur",
            pois=[_poi_dict(CITY_PALACE)],
            total_days=1,
            traveler_constraints={"party_size": 0},
        )


@pytest.mark.asyncio
async def test_rebuild_day_updates_only_target_day(service: ItineraryBuilderService):
    base = await service.build_itinerary(
        city="Jaipur",
        pois=[
            _poi_dict(CITY_PALACE),
            _poi_dict(HAWA_MAHAL),
            _poi_dict(JANTAR_MANTAR),
            _poi_dict(ALBERT_HALL),
            _poi_dict(NAHARGARH),
            _poi_dict(AMBER_FORT),
        ],
        total_days=3,
        start_date="2026-04-01",
    )
    original = base["itinerary"]
    day_one_before = original["days"][0]
    day_three_before = original["days"][2]

    rebuilt = await service.rebuild_day(
        itinerary=original,
        day_number=2,
        pois=[_poi_dict(HAWA_MAHAL), _poi_dict(JANTAR_MANTAR)],
        traveler_constraints={"pace": "fast"},
    )
    updated = rebuilt["itinerary"]

    assert updated["days"][0] == day_one_before
    assert updated["days"][2] == day_three_before
    assert updated["days"][1] != original["days"][1]
    assert updated["traveler_constraints"]["pace"] == "fast"
    Itinerary.model_validate(updated)


@pytest.mark.asyncio
async def test_rebuild_day_without_pois_reuses_existing_day_pois(service: ItineraryBuilderService):
    base = await service.build_itinerary(
        city="Jaipur",
        pois=[_poi_dict(CITY_PALACE), _poi_dict(HAWA_MAHAL), _poi_dict(JANTAR_MANTAR)],
        total_days=1,
    )
    original = base["itinerary"]
    day_before = original["days"][0]

    rebuilt = await service.rebuild_day(
        itinerary=original,
        day_number=1,
        traveler_constraints={"pace": "relaxed"},
    )
    updated = rebuilt["itinerary"]["days"][0]

    before_sights = [a["poi_id"] for a in day_before["activities"] if a.get("poi_id")]
    after_sights = [a["poi_id"] for a in updated["activities"] if a.get("poi_id")]
    # Pace change may add/remove meal/rest slots; sightseeing POIs stay the same.
    assert set(after_sights) == set(before_sights)
    assert len(after_sights) == len(before_sights)


@pytest.mark.asyncio
async def test_rebuild_day_rejects_invalid_day_number(service: ItineraryBuilderService):
    base = await service.build_itinerary(
        city="Jaipur",
        pois=[_poi_dict(CITY_PALACE), _poi_dict(HAWA_MAHAL)],
        total_days=2,
    )

    with pytest.raises(ValueError, match="day_number 3 exceeds total_days 2"):
        await service.rebuild_day(itinerary=base["itinerary"], day_number=3)

    with pytest.raises(ValueError, match="day_number must be at least 1"):
        await service.rebuild_day(itinerary=base["itinerary"], day_number=0)


@pytest.mark.asyncio
async def test_rebuild_day_rejects_invalid_itinerary_payload(service: ItineraryBuilderService):
    with pytest.raises(ValueError, match="invalid itinerary payload"):
        await service.rebuild_day(itinerary={"city": ""}, day_number=1)


@pytest.mark.asyncio
async def test_rebuild_day_rejects_missing_day(service: ItineraryBuilderService):
    invalid = Itinerary(
        city="Jaipur",
        total_days=2,
        days=[],
        traveler_constraints=TravelerConstraints(),
    )
    with pytest.raises(ValueError, match="day_number 1 not found"):
        await service.rebuild_day(itinerary=invalid.model_dump(mode="json"), day_number=1)


def test_itinerary_schema_validation_on_service_output():
    """Round-trip through Pydantic ensures canonical schema compliance."""
    itinerary = Itinerary(
        city="Jaipur",
        total_days=1,
        days=[],
        traveler_constraints=TravelerConstraints(),
    )
    with pytest.raises(ValidationError):
        Itinerary.model_validate({**itinerary.model_dump(mode="json"), "total_days": 0})
