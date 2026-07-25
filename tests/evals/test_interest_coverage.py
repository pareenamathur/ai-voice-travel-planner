"""Interest coverage evaluation tests."""

from src.evals.interest_coverage import evaluate_interest_coverage


def _itinerary_with_activities(*pairs: tuple[str, str]) -> dict:
    activities = []
    registry = []
    for index, (poi_id, category) in enumerate(pairs, start=1):
        activities.append(
            {
                "id": f"d1-a{index}",
                "title": f"Stop {index}",
                "poi_id": poi_id,
                "category": category,
                "duration_minutes": 90,
            }
        )
        registry.append(
            {
                "poi_id": poi_id,
                "name": f"Stop {index}",
                "latitude": 26.9,
                "longitude": 75.8,
                "category": category,
                "source": "osm",
            }
        )
    return {
        "city": "Jaipur",
        "total_days": 1,
        "traveler_constraints": {"interests": ["food", "adventure"]},
        "metadata": {"live_poi_lookup": True},
        "poi_registry": registry,
        "days": [{"day_number": 1, "activities": activities, "travel_segments": []}],
    }


def test_interest_coverage_passes_when_all_interests_present():
    itinerary = _itinerary_with_activities(
        ("node/1", "food"),
        ("node/2", "adventure"),
    )
    report = evaluate_interest_coverage(
        itinerary,
        constraints={"interests": ["food", "adventure"]},
        poi_registry={ref["poi_id"]: ref for ref in itinerary["poi_registry"]},
    )
    assert report.passed is True


def test_interest_coverage_fails_when_adventure_missing():
    itinerary = _itinerary_with_activities(("node/1", "food"), ("node/2", "food"))
    registry = {
        ref["poi_id"]: ref
        for ref in itinerary["poi_registry"]
    }
    registry["node/3"] = {
        "poi_id": "node/3",
        "name": "Adventure Park",
        "latitude": 26.92,
        "longitude": 75.78,
        "category": "adventure",
        "source": "osm",
    }
    report = evaluate_interest_coverage(
        itinerary,
        constraints={"interests": ["food", "adventure"]},
        poi_registry=registry,
    )
    assert report.passed is False
    assert any("adventure" in reason for reason in report.reasons)
