"""Edit correctness evaluation — scope match, no collateral changes, constraints preserved.

Deterministic, no LLM. Runs only on EditArtifacts: compares the edited
itinerary against ``before_snapshot`` and verifies changes stay inside
``edit_scope``.
"""

from __future__ import annotations

from typing import Any

from src.shared.messages.types import EditScope, EvalReportEntry

EVAL_NAME = "edit_correctness"


def evaluate_edit_correctness(
    itinerary: dict[str, Any],
    before_snapshot: dict[str, Any],
    edit_scope: EditScope | dict[str, Any],
) -> EvalReportEntry:
    """Check the edit touched only the scoped day and preserved trip-level constraints."""
    reasons: list[str] = []
    scope = _as_scope(edit_scope)

    before_days = _days_by_number(before_snapshot)
    after_days = _days_by_number(itinerary)

    if scope.day is not None and scope.day not in after_days:
        reasons.append(f"scoped day {scope.day} is missing from the edited itinerary")

    if set(before_days) != set(after_days):
        added = sorted(set(after_days) - set(before_days))
        removed = sorted(set(before_days) - set(after_days))
        if added:
            reasons.append(f"edit added unexpected day(s): {added}")
        if removed:
            reasons.append(f"edit removed day(s): {removed}")

    for day_number, before_day in before_days.items():
        if scope.day is not None and day_number == scope.day:
            continue
        if after_days.get(day_number) != before_day:
            reasons.append(
                f"day {day_number} changed although edit scope was "
                f"{'day ' + str(scope.day) if scope.day is not None else 'unspecified'}"
            )

    for field in ("city", "total_days"):
        if before_snapshot.get(field) != itinerary.get(field):
            reasons.append(
                f"trip-level field '{field}' changed from "
                f"{before_snapshot.get(field)!r} to {itinerary.get(field)!r}"
            )

    return EvalReportEntry(name=EVAL_NAME, passed=not reasons, reasons=reasons)


def _as_scope(edit_scope: EditScope | dict[str, Any]) -> EditScope:
    if isinstance(edit_scope, EditScope):
        return edit_scope
    return EditScope.model_validate(edit_scope or {})


def _days_by_number(itinerary: dict[str, Any]) -> dict[int, dict[str, Any]]:
    days: dict[int, dict[str, Any]] = {}
    for day in itinerary.get("days") or []:
        if isinstance(day, dict) and day.get("day_number") is not None:
            days[int(day["day_number"])] = day
    return days
