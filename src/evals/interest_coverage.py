"""Interest coverage evaluation — requested traveler interests appear in the itinerary."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.shared.interests import missing_interests, normalize_interests, poi_satisfies_interest
from src.shared.itinerary import Itinerary
from src.shared.messages.types import EvalReportEntry

EVAL_NAME = "interest_coverage"


def evaluate_interest_coverage(
    itinerary: dict[str, Any],
    *,
    constraints: dict[str, Any] | None = None,
    poi_registry: dict[str, Any] | None = None,
) -> EvalReportEntry:
    """Fail when an explicitly requested interest has no matching scheduled activity."""
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

    requested = normalize_interests(
        (constraints or {}).get("interests")
        or model.traveler_constraints.interests
    )
    if not requested:
        return EvalReportEntry(name=EVAL_NAME, passed=True, reasons=[])

    registry = dict(poi_registry or {})
    registry_pois = [dict(value) for value in registry.values()]
    enforceable = [
        interest
        for interest in requested
        if any(poi_satisfies_interest(poi, interest) for poi in registry_pois)
    ]
    if not enforceable:
        return EvalReportEntry(name=EVAL_NAME, passed=True, reasons=[])

    scheduled_pois: list[dict[str, Any]] = []
    for day in model.days:
        for activity in day.activities:
            if not activity.poi_id:
                continue
            ref = registry.get(str(activity.poi_id))
            if ref:
                scheduled_pois.append(dict(ref))
                continue
            scheduled_pois.append(
                {
                    "osm_id": activity.poi_id,
                    "name": activity.title,
                    "category": activity.category,
                }
            )

    absent = missing_interests(enforceable, scheduled_pois)
    if not absent:
        return EvalReportEntry(name=EVAL_NAME, passed=True, reasons=[])

    reasons = [
        f"missing coverage for requested interest '{interest}'"
        for interest in absent
    ]
    return EvalReportEntry(name=EVAL_NAME, passed=False, reasons=reasons)
