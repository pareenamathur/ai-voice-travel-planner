"""Grounding & hallucination evaluation — POI identity, citations, disclaimers.

Deterministic, no LLM. An itinerary is grounded when every scheduled activity
traces back to a known POI reference (OSM or curated fallback), at least one
grounding source exists (POI registry, RAG citations, or document citations),
and degraded live-data lookups carry a user-facing disclaimer.
"""

from __future__ import annotations

from typing import Any

from src.shared.messages.types import EvalReportEntry

EVAL_NAME = "grounding"

VALID_POI_ID_PREFIXES = ("node/", "way/", "relation/", "well_known/", "llm/")


def evaluate_grounding(
    itinerary: dict[str, Any],
    poi_registry: dict[str, Any] | None = None,
    rag_citations: list[dict[str, Any]] | None = None,
) -> EvalReportEntry:
    """Check POI id validity, activity-to-registry traceability, citations, disclaimers."""
    reasons: list[str] = []
    registry = poi_registry or {}
    citations = rag_citations or []

    embedded_registry = [
        ref for ref in (itinerary.get("poi_registry") or []) if isinstance(ref, dict)
    ]
    known_ids = set(registry.keys()) | {
        str(ref.get("poi_id")) for ref in embedded_registry if ref.get("poi_id")
    }

    for poi_id in sorted(known_ids):
        if not _is_valid_poi_id(poi_id):
            reasons.append(f"POI id '{poi_id}' does not match any known source format")

    activities = [
        (day.get("day_number"), activity)
        for day in (itinerary.get("days") or [])
        for activity in (day.get("activities") or [])
        if isinstance(activity, dict)
    ]

    for day_number, activity in activities:
        poi_id = activity.get("poi_id")
        if not poi_id:
            continue
        if str(poi_id) not in known_ids:
            reasons.append(
                f"day {day_number}: activity '{activity.get('title', activity.get('id'))}' "
                f"references unknown POI '{poi_id}'"
            )

    has_grounding_source = bool(
        known_ids or citations or itinerary.get("citations")
    )
    if activities and not has_grounding_source:
        reasons.append(
            "itinerary has scheduled activities but no POI registry entries or citations"
        )

    metadata = itinerary.get("metadata") or {}
    if "live_poi_lookup" in metadata and not metadata.get("live_poi_lookup"):
        if not str(metadata.get("user_note") or "").strip():
            reasons.append(
                "live POI lookup was degraded but no user-facing disclaimer "
                "(metadata.user_note) is present"
            )

    return EvalReportEntry(name=EVAL_NAME, passed=not reasons, reasons=reasons)


def _is_valid_poi_id(poi_id: str) -> bool:
    return poi_id.startswith(VALID_POI_ID_PREFIXES) and len(poi_id.split("/", 1)[1]) > 0
