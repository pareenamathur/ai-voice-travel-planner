"""Export Service — builds downloadable itinerary artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from src.export.renderers import render_markdown, render_pdf
from src.shared.itinerary import Itinerary


class ExportFormat(StrEnum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"


class ExportService:
    """Pure export logic used by the MCP ``trigger_export`` tool."""

    def export(
        self,
        *,
        itinerary: dict[str, Any],
        export_format: str,
        trip_title: str | None = None,
        extra_citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        fmt = ExportFormat(export_format.lower())
        model = Itinerary.model_validate(itinerary)
        generated_at = datetime.now(UTC)
        title = trip_title or _default_trip_title(model)
        context = _build_export_context(
            model,
            trip_title=title,
            generated_at=generated_at,
            extra_citations=extra_citations or [],
        )

        if fmt == ExportFormat.JSON:
            payload = model.model_dump(mode="json")
            payload.setdefault("metadata", {})
            if isinstance(payload["metadata"], dict):
                payload["metadata"]["export_generated_at"] = generated_at.isoformat()
                payload["metadata"]["trip_title"] = title
            content = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            media_type = "application/json"
            filename = _slug_filename(model.city, "json")
        elif fmt == ExportFormat.MARKDOWN:
            content = render_markdown(context).encode("utf-8")
            media_type = "text/markdown; charset=utf-8"
            filename = _slug_filename(model.city, "md")
        else:
            content = render_pdf(context)
            media_type = "application/pdf"
            filename = _slug_filename(model.city, "pdf")

        return {
            "format": fmt.value,
            "filename": filename,
            "media_type": media_type,
            "content": content,
            "trip_title": title,
            "generated_at": generated_at.isoformat(),
        }


def _default_trip_title(itinerary: Itinerary) -> str:
    city = itinerary.city.strip().title()
    days = itinerary.total_days or len(itinerary.days) or 1
    return f"{city} — {days}-Day Trip"


def _slug_filename(city: str, extension: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in city.lower()).strip("-")
    slug = slug or "trip"
    return f"{slug}-itinerary.{extension}"


def _build_export_context(
    itinerary: Itinerary,
    *,
    trip_title: str,
    generated_at: datetime,
    extra_citations: list[dict[str, Any]],
) -> dict[str, Any]:
    days_out: list[dict[str, Any]] = []
    food_recs: list[str] = []
    shopping_recs: list[str] = []

    for day in sorted(itinerary.days, key=lambda d: d.day_number):
        blocks: dict[str, list[dict[str, Any]]] = {
            "morning": [],
            "afternoon": [],
            "evening": [],
        }
        travel_notes: list[str] = []

        for activity in day.activities:
            category = str(activity.category or "").lower()
            entry = {
                "title": activity.title,
                "start": activity.start_time,
                "end": activity.end_time,
                "duration_minutes": activity.duration_minutes,
                "category": category or None,
                "notes": activity.notes,
            }
            period = _period_for_activity(activity.start_time)
            blocks[period].append(entry)
            if category == "food":
                food_recs.append(_activity_label(activity))
            if category == "shopping":
                shopping_recs.append(_activity_label(activity))

        for segment in day.travel_segments:
            travel_notes.append(
                f"{segment.travel_minutes} min {str(segment.transport_mode).replace('_', ' ')}"
                + (f" — {segment.notes}" if segment.notes else "")
            )

        days_out.append(
            {
                "day_number": day.day_number,
                "date": day.date.isoformat() if day.date else None,
                "notes": day.notes,
                "blocks": blocks,
                "travel_notes": travel_notes,
            }
        )

    sources = _collect_sources(itinerary, extra_citations)
    pace = itinerary.traveler_constraints.pace
    interests = list(itinerary.traveler_constraints.interests or [])

    return {
        "trip_title": trip_title,
        "city": itinerary.city,
        "total_days": itinerary.total_days,
        "generated_at": generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        "generated_at_iso": generated_at.isoformat(),
        "pace": pace,
        "interests": interests,
        "days": days_out,
        "food_recommendations": _dedupe_preserve(food_recs),
        "shopping_recommendations": _dedupe_preserve(shopping_recs),
        "trip_notes": itinerary.metadata.get("notes") if itinerary.metadata else None,
        "sources": sources,
    }


def _period_for_activity(start_time: str | None) -> str:
    if not start_time:
        return "afternoon"
    try:
        hours, minutes = start_time.split(":")
        total = int(hours) * 60 + int(minutes)
    except ValueError:
        return "afternoon"
    if total < 12 * 60:
        return "morning"
    if total < 17 * 60:
        return "afternoon"
    return "evening"


def _activity_label(activity) -> str:
    parts = [activity.title]
    if activity.start_time:
        parts.append(f"({activity.start_time})")
    return " ".join(parts)


def _collect_sources(
    itinerary: Itinerary,
    extra: list[dict[str, Any]],
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        cleaned = label.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        labels.append(cleaned)

    for citation in itinerary.citations:
        label = citation.section or citation.source_url or citation.citation_id
        if label:
            add(str(label))

    for citation in extra:
        if isinstance(citation, dict):
            label = (
                citation.get("label")
                or citation.get("section")
                or citation.get("source_url")
                or citation.get("citation_id")
            )
            if label:
                add(str(label))

    return labels


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def safe_validate_itinerary(itinerary: dict[str, Any]) -> Itinerary | None:
    try:
        return Itinerary.model_validate(itinerary)
    except ValidationError:
        return None
