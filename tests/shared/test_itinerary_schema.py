"""Phase 3 Task 1 — canonical itinerary schema tests."""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError
from src.shared.itinerary import (
    Activity,
    ActivityCategory,
    Itinerary,
    TransportMode,
    TravelSegment,
)

SAMPLE_ITINERARY = {
    "city": "jaipur",
    "total_days": 2,
    "start_date": "2026-04-01",
    "traveler_constraints": {
        "interests": ["culture", "food"],
        "pace": "relaxed",
        "party_size": 2,
        "daily_window_start": "09:00",
        "daily_window_end": "21:00",
    },
    "poi_registry": [
        {
            "poi_id": "node/123",
            "name": "City Palace",
            "latitude": 26.9855,
            "longitude": 75.8513,
            "category": "culture",
            "source": "osm",
        }
    ],
    "citations": [
        {
            "citation_id": "jaipur:wikivoyage#see#0001",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            "section": "See",
        }
    ],
    "days": [
        {
            "day_number": 1,
            "date": "2026-04-01",
            "notes": "Arrival day",
            "activities": [
                {
                    "id": "d1-a1",
                    "title": "City Palace",
                    "poi_id": "node/123",
                    "category": "culture",
                    "latitude": 26.9855,
                    "longitude": 75.8513,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "duration_minutes": 120,
                    "notes": "Buy combo ticket",
                    "citations": [
                        {
                            "citation_id": "jaipur:wikivoyage#see#0001",
                            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
                            "section": "See",
                        }
                    ],
                },
                {
                    "id": "d1-a2",
                    "title": "Lunch near Hawa Mahal",
                    "category": "food",
                    "start_time": "12:30",
                    "end_time": "13:30",
                    "duration_minutes": 60,
                },
            ],
            "travel_segments": [
                {
                    "from_activity_id": "d1-a1",
                    "to_activity_id": "d1-a2",
                    "travel_minutes": 15,
                    "transport_mode": "walk",
                    "notes": "Short walk through old city",
                }
            ],
        },
        {
            "day_number": 2,
            "date": "2026-04-02",
            "activities": [],
            "travel_segments": [],
        },
    ],
    "metadata": {"schema_version": "1.0"},
}


def test_itinerary_parses_valid_sample():
    itinerary = Itinerary.model_validate(SAMPLE_ITINERARY)

    assert itinerary.city == "jaipur"
    assert itinerary.total_days == 2
    assert itinerary.start_date == date(2026, 4, 1)
    assert itinerary.traveler_constraints.pace == "relaxed"
    assert len(itinerary.days) == 2
    assert itinerary.days[0].activities[0].poi_id == "node/123"
    assert itinerary.days[0].travel_segments[0].travel_minutes == 15
    assert itinerary.poi_registry[0].name == "City Palace"
    assert itinerary.citations[0].citation_id.startswith("jaipur:")


def test_itinerary_json_round_trip():
    itinerary = Itinerary.model_validate(SAMPLE_ITINERARY)
    payload = json.loads(itinerary.model_dump_json())
    restored = Itinerary.model_validate(payload)

    assert restored == itinerary


def test_itinerary_json_schema_has_required_models():
    schema = Itinerary.model_json_schema()
    defs = schema.get("$defs", {})

    assert "Activity" in defs
    assert "DayPlan" in defs
    assert "TravelSegment" in defs
    assert "properties" in schema
    assert "city" in schema["properties"]
    assert "total_days" in schema["properties"]
    assert "days" in schema["properties"]


def test_activity_requires_id_and_title():
    with pytest.raises(ValidationError):
        Activity.model_validate({"id": "x", "title": ""})


def test_travel_segment_requires_positive_travel_minutes():
    with pytest.raises(ValidationError):
        TravelSegment.model_validate(
            {
                "from_activity_id": "a",
                "to_activity_id": "b",
                "travel_minutes": -1,
            }
        )


def test_itinerary_rejects_duplicate_day_numbers():
    payload = {
        **SAMPLE_ITINERARY,
        "days": [
            {"day_number": 1, "activities": [], "travel_segments": []},
            {"day_number": 1, "activities": [], "travel_segments": []},
        ],
    }
    with pytest.raises(ValidationError, match="day_number values must be unique"):
        Itinerary.model_validate(payload)


def test_itinerary_rejects_more_days_than_total_days():
    payload = {
        **SAMPLE_ITINERARY,
        "total_days": 1,
    }
    with pytest.raises(ValidationError, match="days length cannot exceed total_days"):
        Itinerary.model_validate(payload)


def test_activity_accepts_enum_and_string_category():
    activity = Activity.model_validate(
        {
            "id": "a1",
            "title": "Museum visit",
            "category": ActivityCategory.CULTURE,
        }
    )
    assert activity.category == ActivityCategory.CULTURE

    custom = Activity.model_validate(
        {
            "id": "a2",
            "title": "Local market",
            "category": "markets",
        }
    )
    assert custom.category == "markets"


def test_travel_segment_accepts_transport_mode_enum():
    segment = TravelSegment.model_validate(
        {
            "from_activity_id": "a",
            "to_activity_id": "b",
            "travel_minutes": 10,
            "transport_mode": TransportMode.TRANSIT,
        }
    )
    assert segment.transport_mode == TransportMode.TRANSIT
