"""Edit correctness eval module tests (Phase 7 Task 1)."""

from __future__ import annotations

import copy
from typing import Any

from src.evals.edit_correctness import evaluate_edit_correctness
from src.shared.messages.types import EditScope


def _two_day_itinerary() -> dict[str, Any]:
    return {
        "city": "Jaipur",
        "total_days": 2,
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {"id": "d1-a1", "title": "City Palace", "duration_minutes": 90}
                ],
                "travel_segments": [],
            },
            {
                "day_number": 2,
                "activities": [
                    {"id": "d2-a1", "title": "Amber Fort", "duration_minutes": 90}
                ],
                "travel_segments": [],
            },
        ],
    }


def test_scoped_edit_passes() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)
    after["days"][1]["activities"][0]["duration_minutes"] = 60

    entry = evaluate_edit_correctness(after, before, EditScope(day=2, intent="relax day 2"))
    assert entry.name == "edit_correctness"
    assert entry.passed
    assert entry.reasons == []


def test_collateral_change_fails() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)
    after["days"][1]["activities"][0]["duration_minutes"] = 60
    after["days"][0]["activities"][0]["title"] = "City Palace Extended Tour"

    entry = evaluate_edit_correctness(after, before, {"day": 2, "intent": "relax day 2"})
    assert not entry.passed
    assert any("day 1 changed" in reason for reason in entry.reasons)


def test_missing_scoped_day_fails() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)

    entry = evaluate_edit_correctness(after, before, EditScope(day=5, intent="edit day 5"))
    assert not entry.passed
    assert any("scoped day 5 is missing" in reason for reason in entry.reasons)


def test_removed_day_fails() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)
    after["days"] = after["days"][:1]

    entry = evaluate_edit_correctness(after, before, EditScope(day=1, intent="edit day 1"))
    assert not entry.passed
    assert any("removed day(s)" in reason for reason in entry.reasons)


def test_trip_level_field_change_fails() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)
    after["days"][1]["activities"][0]["duration_minutes"] = 60
    after["city"] = "Udaipur"

    entry = evaluate_edit_correctness(after, before, EditScope(day=2, intent="relax day 2"))
    assert not entry.passed
    assert any("'city' changed" in reason for reason in entry.reasons)


def test_unscoped_edit_requires_no_day_changes_elsewhere() -> None:
    before = _two_day_itinerary()
    after = copy.deepcopy(before)
    after["days"][0]["activities"][0]["duration_minutes"] = 45

    entry = evaluate_edit_correctness(after, before, EditScope(intent="generic edit"))
    assert not entry.passed
    assert any("edit scope was unspecified" in reason for reason in entry.reasons)
