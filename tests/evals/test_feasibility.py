"""Feasibility eval module tests (Phase 7 Task 1)."""

from __future__ import annotations

from typing import Any

from src.evals.feasibility import (
    DEFAULT_DAILY_BUDGET_MINUTES,
    MAX_SINGLE_TRAVEL_MINUTES,
    evaluate_feasibility,
)


def _itinerary(
    *,
    pace: str = "moderate",
    activities: list[dict[str, Any]] | None = None,
    travel_segments: list[dict[str, Any]] | None = None,
    constraints_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "city": "Jaipur",
        "total_days": 1,
        "traveler_constraints": {"pace": pace, **(constraints_extra or {})},
        "days": [
            {
                "day_number": 1,
                "activities": activities
                or [
                    {"id": "d1-a1", "title": "City Palace", "duration_minutes": 90},
                    {"id": "d1-a2", "title": "Hawa Mahal", "duration_minutes": 90},
                ],
                "travel_segments": travel_segments or [],
            }
        ],
    }


def test_healthy_day_passes() -> None:
    entry = evaluate_feasibility(_itinerary())
    assert entry.name == "feasibility"
    assert entry.passed
    assert entry.reasons == []


def test_overbudget_day_fails() -> None:
    activities = [
        {"id": f"d1-a{i}", "title": f"Stop {i}", "duration_minutes": 180} for i in range(1, 5)
    ]
    entry = evaluate_feasibility(_itinerary(activities=activities))
    assert not entry.passed
    assert any(str(DEFAULT_DAILY_BUDGET_MINUTES) in reason for reason in entry.reasons)


def test_travel_counts_toward_daily_budget() -> None:
    activities = [
        {"id": "d1-a1", "title": "A", "duration_minutes": 280},
        {"id": "d1-a2", "title": "B", "duration_minutes": 280},
    ]
    segments = [
        {"from_activity_id": "d1-a1", "to_activity_id": "d1-a2", "travel_minutes": 60}
    ]
    entry = evaluate_feasibility(_itinerary(activities=activities, travel_segments=segments))
    assert not entry.passed


def test_single_travel_leg_over_threshold_fails() -> None:
    segments = [
        {
            "from_activity_id": "d1-a1",
            "to_activity_id": "d1-a2",
            "travel_minutes": MAX_SINGLE_TRAVEL_MINUTES + 30,
        }
    ]
    entry = evaluate_feasibility(_itinerary(travel_segments=segments))
    assert not entry.passed
    assert any("travel leg" in reason for reason in entry.reasons)


def test_relaxed_pace_activity_cap() -> None:
    activities = [
        {"id": f"d1-a{i}", "title": f"Stop {i}", "duration_minutes": 60} for i in range(1, 8)
    ]
    entry = evaluate_feasibility(_itinerary(pace="relaxed", activities=activities))
    assert not entry.passed
    assert any("relaxed" in reason for reason in entry.reasons)


def test_explicit_daily_window_overrides_default() -> None:
    activities = [{"id": "d1-a1", "title": "A", "duration_minutes": 200}]
    itinerary = _itinerary(
        activities=activities,
        constraints_extra={"daily_window_start": "09:00", "daily_window_end": "11:00"},
    )
    entry = evaluate_feasibility(itinerary)
    assert not entry.passed
    assert any("120 min daily window" in reason for reason in entry.reasons)


def test_invalid_schema_fails_with_reason() -> None:
    entry = evaluate_feasibility({"city": "Jaipur"})
    assert not entry.passed
    assert any("schema validation" in reason for reason in entry.reasons)
