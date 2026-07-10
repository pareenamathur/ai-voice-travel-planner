"""Phase 3 Task 2 — scheduling and travel time tests."""

from __future__ import annotations

from datetime import date

from src.mcp_servers.itinerary_builder.scheduler import (
    group_nearby_pois,
    schedule_itinerary,
)
from src.mcp_servers.itinerary_builder.travel import (
    estimate_travel_time,
    haversine_distance_km,
    infer_transport_mode,
)
from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import TransportMode, TravelerConstraints

# Jaipur-area sample POIs
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
AMBER_FORT = POI(
    osm_id="node/4",
    name="Amber Fort",
    lat=26.9855,
    lon=75.8513,
    category="sightseeing",
)
NAHARGARH = POI(
    osm_id="node/5",
    name="Nahargarh Fort",
    lat=26.9376,
    lon=75.8155,
    category="sightseeing",
)
ALBERT_HALL = POI(
    osm_id="node/6",
    name="Albert Hall Museum",
    lat=26.9115,
    lon=75.8195,
    category="culture",
)


def _poi(osm_id: str, name: str, lat: float, lon: float) -> POI:
    return POI(osm_id=osm_id, name=name, lat=lat, lon=lon, category="culture")


def test_estimate_travel_time_uses_haversine_and_caps_at_45_minutes():
    near = estimate_travel_time(CITY_PALACE, HAWA_MAHAL)
    far = estimate_travel_time(CITY_PALACE, _poi("node/far", "Far POI", 27.5, 76.5))

    assert 0 < near <= 45
    assert far == 45


def test_infer_transport_mode_prefers_walk_for_short_legs():
    close_a = _poi("node/a", "Close A", 26.9120, 75.8200)
    close_b = _poi("node/b", "Close B", 26.9125, 75.8205)
    short_distance = haversine_distance_km(close_a.lat, close_a.lon, close_b.lat, close_b.lon)
    assert infer_transport_mode(short_distance) == TransportMode.WALK
    assert infer_transport_mode(5.0) == TransportMode.DRIVE


def test_group_nearby_pois_clusters_close_locations():
    clusters = group_nearby_pois(
        [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR, AMBER_FORT],
        radius_km=2.0,
    )
    flat = [poi.osm_id for cluster in clusters for poi in cluster]

    assert sorted(flat) == sorted(["node/1", "node/2", "node/3", "node/4"])
    assert any(len(cluster) >= 2 for cluster in clusters)


def test_schedule_itinerary_one_day():
    pois = [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR]
    itinerary = schedule_itinerary(
        city="jaipur",
        pois=pois,
        total_days=1,
        start_date=date(2026, 4, 1),
    )

    assert itinerary.total_days == 1
    assert len(itinerary.days) == 1
    assert len(itinerary.days[0].activities) >= 1
    assert itinerary.days[0].activities[0].start_time >= "09:00"


def test_schedule_itinerary_two_days_balances_allocation():
    pois = [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR, ALBERT_HALL]
    itinerary = schedule_itinerary(city="jaipur", pois=pois, total_days=2)

    counts = [len(day.activities) for day in itinerary.days]
    assert len(itinerary.days) == 2
    assert max(counts) - min(counts) <= 1
    assert sum(counts) >= 3


def test_schedule_itinerary_three_days():
    pois = [CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR, ALBERT_HALL, NAHARGARH, AMBER_FORT]
    itinerary = schedule_itinerary(city="jaipur", pois=pois, total_days=3)

    assert itinerary.total_days == 3
    assert len(itinerary.days) == 3
    scheduled_ids = {
        activity.poi_id for day in itinerary.days for activity in day.activities if activity.poi_id
    }
    assert len(scheduled_ids) >= 4


def test_schedule_itinerary_removes_duplicate_pois():
    duplicate = POI(
        osm_id="node/1",
        name="City Palace Duplicate",
        lat=26.9855,
        lon=75.8513,
        category="culture",
    )
    itinerary = schedule_itinerary(
        city="jaipur",
        pois=[CITY_PALACE, duplicate, HAWA_MAHAL],
        total_days=1,
    )

    poi_ids = [activity.poi_id for day in itinerary.days for activity in day.activities]
    assert poi_ids.count("node/1") <= 1
    assert len(itinerary.poi_registry) <= 2


def test_schedule_day_includes_travel_segments_between_activities():
    itinerary = schedule_itinerary(
        city="jaipur",
        pois=[CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR],
        total_days=1,
    )
    day = itinerary.days[0]

    if len(day.activities) >= 2:
        assert len(day.travel_segments) >= 1
        segment = day.travel_segments[0]
        assert segment.travel_minutes >= 0
        assert segment.from_activity_id != segment.to_activity_id


def test_activities_start_within_sightseeing_window():
    itinerary = schedule_itinerary(
        city="jaipur",
        pois=[CITY_PALACE, HAWA_MAHAL, JANTAR_MANTAR, ALBERT_HALL],
        total_days=2,
        traveler_constraints=TravelerConstraints(pace="moderate"),
    )

    for day in itinerary.days:
        for activity in day.activities:
            assert activity.start_time is not None
            hour = int(activity.start_time.split(":")[0])
            assert 9 <= hour <= 18
