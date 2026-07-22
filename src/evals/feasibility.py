"""Feasibility evaluation — daily time budget, travel limits, pace consistency.

Deterministic, no LLM. Runs on the canonical itinerary document from a
PlanArtifact or EditArtifact. Thresholds mirror the itinerary-builder
scheduler so healthy runtime artifacts pass without slack-tuning.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.shared.itinerary import Itinerary
from src.shared.messages.types import EvalReportEntry

EVAL_NAME = "feasibility"

# Matches scheduler MAX_DAY_MINUTES (activities + travel + meal breaks per day).
DEFAULT_DAILY_BUDGET_MINUTES = 720
MAX_SINGLE_TRAVEL_MINUTES = 90
MAX_DAILY_TRAVEL_MINUTES = 240
# Includes lunch/tea/dinner/return slots produced by the full-day scheduler.
MAX_ACTIVITIES_BY_PACE = {"relaxed": 8, "moderate": 10, "fast": 12, "packed": 12}
DEFAULT_MAX_ACTIVITIES = 10


def evaluate_feasibility(itinerary: dict[str, Any]) -> EvalReportEntry:
    """Check daily duration budget, travel thresholds, and pace consistency."""
    try:
        model = Itinerary.model_validate(itinerary)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(loc) for loc in first.get("loc", []))
        detail = f"{location}: {first.get('msg', 'invalid')}"
        return EvalReportEntry(
            name=EVAL_NAME,
            passed=False,
            reasons=[f"itinerary failed schema validation ({detail})"],
        )

    reasons: list[str] = []
    budget = _daily_budget_minutes(model)
    pace = (model.traveler_constraints.pace or "moderate").lower()
    max_activities = MAX_ACTIVITIES_BY_PACE.get(pace, DEFAULT_MAX_ACTIVITIES)

    for day in model.days:
        activity_minutes = sum(a.duration_minutes or 0 for a in day.activities)
        travel_minutes = sum(seg.travel_minutes for seg in day.travel_segments)
        total = activity_minutes + travel_minutes

        if total > budget:
            reasons.append(
                f"day {day.day_number}: scheduled {total} min exceeds the "
                f"{budget} min daily window"
            )
        if travel_minutes > MAX_DAILY_TRAVEL_MINUTES:
            reasons.append(
                f"day {day.day_number}: total travel {travel_minutes} min exceeds "
                f"{MAX_DAILY_TRAVEL_MINUTES} min"
            )
        for seg in day.travel_segments:
            if seg.travel_minutes > MAX_SINGLE_TRAVEL_MINUTES:
                reasons.append(
                    f"day {day.day_number}: travel leg {seg.from_activity_id} -> "
                    f"{seg.to_activity_id} takes {seg.travel_minutes} min "
                    f"(max {MAX_SINGLE_TRAVEL_MINUTES})"
                )
        if len(day.activities) > max_activities:
            reasons.append(
                f"day {day.day_number}: {len(day.activities)} activities exceeds "
                f"{max_activities} allowed for '{pace}' pace"
            )

    return EvalReportEntry(name=EVAL_NAME, passed=not reasons, reasons=reasons)


def _daily_budget_minutes(itinerary: Itinerary) -> int:
    constraints = itinerary.traveler_constraints
    if constraints.daily_window_start and constraints.daily_window_end:
        window = _to_minutes(constraints.daily_window_end) - _to_minutes(
            constraints.daily_window_start
        )
        if window > 0:
            return window
    return DEFAULT_DAILY_BUDGET_MINUTES


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)
