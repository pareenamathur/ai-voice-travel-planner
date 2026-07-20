"""Grounding eval module tests (Phase 7 Task 1)."""

from __future__ import annotations

from typing import Any

from src.evals.grounding import evaluate_grounding


def _itinerary(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "city": "Jaipur",
        "total_days": 1,
        "metadata": {"live_poi_lookup": True},
        "poi_registry": [
            {
                "poi_id": "well_known/jaipur-city-palace",
                "name": "City Palace",
                "latitude": 26.9258,
                "longitude": 75.8237,
                "source": "well_known",
            }
        ],
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "id": "d1-a1",
                        "title": "City Palace",
                        "poi_id": "well_known/jaipur-city-palace",
                        "duration_minutes": 90,
                    }
                ],
                "travel_segments": [],
            }
        ],
    }
    base.update(overrides)
    return base


def test_grounded_itinerary_passes() -> None:
    entry = evaluate_grounding(_itinerary())
    assert entry.name == "grounding"
    assert entry.passed
    assert entry.reasons == []


def test_osm_node_ids_are_valid() -> None:
    itinerary = _itinerary(
        poi_registry=[
            {
                "poi_id": "node/123456",
                "name": "City Palace",
                "latitude": 26.9258,
                "longitude": 75.8237,
                "source": "osm",
            }
        ]
    )
    itinerary["days"][0]["activities"][0]["poi_id"] = "node/123456"
    assert evaluate_grounding(itinerary).passed


def test_fake_poi_id_format_fails() -> None:
    itinerary = _itinerary(
        poi_registry=[
            {
                "poi_id": "fake:amber-fort",
                "name": "Amber Fort",
                "latitude": 26.9855,
                "longitude": 75.8513,
            }
        ]
    )
    itinerary["days"][0]["activities"][0]["poi_id"] = "fake:amber-fort"
    entry = evaluate_grounding(itinerary)
    assert not entry.passed
    assert any("known source format" in reason for reason in entry.reasons)


def test_activity_referencing_unknown_poi_fails() -> None:
    itinerary = _itinerary()
    itinerary["days"][0]["activities"].append(
        {"id": "d1-a2", "title": "Secret Palace", "poi_id": "node/99999"}
    )
    entry = evaluate_grounding(itinerary)
    assert not entry.passed
    assert any("unknown POI" in reason for reason in entry.reasons)


def test_artifact_level_registry_counts_as_known() -> None:
    itinerary = _itinerary(poi_registry=[])
    itinerary["days"][0]["activities"][0]["poi_id"] = "node/123"
    registry = {"node/123": {"osm_id": "node/123", "name": "City Palace"}}
    assert evaluate_grounding(itinerary, poi_registry=registry).passed


def test_no_grounding_sources_fails() -> None:
    itinerary = _itinerary(poi_registry=[])
    itinerary["days"][0]["activities"][0].pop("poi_id")
    entry = evaluate_grounding(itinerary)
    assert not entry.passed
    assert any("no POI registry entries or citations" in reason for reason in entry.reasons)


def test_rag_citations_count_as_grounding_source() -> None:
    itinerary = _itinerary(poi_registry=[])
    itinerary["days"][0]["activities"][0].pop("poi_id")
    citations = [{"citation_id": "wikivoyage-jaipur-1", "source_url": "https://example.org"}]
    assert evaluate_grounding(itinerary, rag_citations=citations).passed


def test_degraded_lookup_without_disclaimer_fails() -> None:
    itinerary = _itinerary(metadata={"live_poi_lookup": False})
    entry = evaluate_grounding(itinerary)
    assert not entry.passed
    assert any("disclaimer" in reason for reason in entry.reasons)


def test_degraded_lookup_with_disclaimer_passes() -> None:
    itinerary = _itinerary(
        metadata={
            "live_poi_lookup": False,
            "user_note": "Live place lookup was temporarily unavailable.",
        }
    )
    assert evaluate_grounding(itinerary).passed
