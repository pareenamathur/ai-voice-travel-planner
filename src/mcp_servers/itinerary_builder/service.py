"""Itinerary Builder service exposed as MCP tools (Phase 3 Task 3)."""

from __future__ import annotations

from datetime import date as Date
from typing import Any

from src.mcp_servers.itinerary_builder.models import (
    constraints_from_dict,
    itinerary_from_dict,
    merge_constraints,
    poi_to_reference,
    pois_from_dicts,
    reference_to_poi,
)
from src.mcp_servers.itinerary_builder.scheduler import schedule_day, schedule_itinerary
from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import DayPlan, Itinerary, PoiReference


class ItineraryBuilderService:
    """Deterministic itinerary construction via ``build_itinerary`` and ``rebuild_day``."""

    async def build_itinerary(
        self,
        *,
        city: str,
        pois: list[dict[str, Any]],
        total_days: int,
        traveler_constraints: dict[str, Any] | None = None,
        start_date: str | None = None,
    ) -> dict[str, Any]:
        """MCP tool handler for ``build_itinerary``.

        Returns a JSON-serializable payload:
        - ``itinerary``: canonical itinerary dict
        - ``source``: ``itinerary_builder``
        """
        normalized_city = city.strip()
        if not normalized_city:
            raise ValueError("city is required")

        if total_days < 1:
            raise ValueError("total_days must be at least 1")

        parsed_pois = pois_from_dicts(pois)
        constraints = constraints_from_dict(traveler_constraints)
        parsed_start: Date | None = None
        if start_date is not None:
            try:
                parsed_start = Date.fromisoformat(start_date)
            except ValueError as exc:
                raise ValueError(f"invalid start_date: {start_date}") from exc

        itinerary = schedule_itinerary(
            city=normalized_city,
            pois=parsed_pois,
            traveler_constraints=constraints,
            total_days=total_days,
            start_date=parsed_start,
        )
        return _tool_response(itinerary)

    async def rebuild_day(
        self,
        *,
        itinerary: dict[str, Any],
        day_number: int,
        pois: list[dict[str, Any]] | None = None,
        traveler_constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """MCP tool handler for ``rebuild_day``.

        Re-schedules a single day while leaving all other days unchanged.
        """
        if day_number < 1:
            raise ValueError("day_number must be at least 1")

        existing = itinerary_from_dict(itinerary)
        if day_number > existing.total_days:
            raise ValueError(f"day_number {day_number} exceeds total_days {existing.total_days}")

        day_index = _find_day_index(existing.days, day_number)
        if day_index is None:
            raise ValueError(f"day_number {day_number} not found in itinerary")

        constraints = merge_constraints(
            existing.traveler_constraints,
            constraints_from_dict(traveler_constraints) if traveler_constraints else None,
        )

        registry_by_id = {ref.poi_id: ref for ref in existing.poi_registry}
        existing_day = existing.days[day_index]
        if pois is not None:
            day_pois = pois_from_dicts(pois)
        else:
            day_pois = _pois_from_day(existing_day, registry_by_id)

        rebuilt_day = schedule_day(
            day_number=day_number,
            pois=day_pois,
            constraints=constraints,
            plan_date=existing_day.date,
        )

        updated_days = list(existing.days)
        updated_days[day_index] = rebuilt_day

        known_pois = _collect_known_pois(existing.poi_registry, day_pois)
        poi_registry = _build_poi_registry(updated_days, known_pois)

        updated = Itinerary(
            city=existing.city,
            total_days=existing.total_days,
            start_date=existing.start_date,
            traveler_constraints=constraints,
            days=updated_days,
            poi_registry=poi_registry,
            citations=list(existing.citations),
            metadata=dict(existing.metadata),
        )
        return _tool_response(updated)


def build_default_itinerary_service() -> ItineraryBuilderService:
    return ItineraryBuilderService()


def _tool_response(itinerary: Itinerary) -> dict[str, Any]:
    return {
        "source": "itinerary_builder",
        "itinerary": itinerary.model_dump(mode="json"),
    }


def _find_day_index(days: list[DayPlan], day_number: int) -> int | None:
    for index, day in enumerate(days):
        if day.day_number == day_number:
            return index
    return None


def _pois_from_day(day: DayPlan, registry_by_id: dict[str, PoiReference]) -> list[POI]:
    pois: list[POI] = []
    for activity in day.activities:
        if activity.poi_id and activity.poi_id in registry_by_id:
            pois.append(reference_to_poi(registry_by_id[activity.poi_id]))
            continue
        if activity.latitude is not None and activity.longitude is not None:
            pois.append(
                POI(
                    osm_id=activity.poi_id or activity.id,
                    name=activity.title,
                    lat=activity.latitude,
                    lon=activity.longitude,
                    category=str(activity.category) if activity.category is not None else None,
                )
            )
    return pois


def _collect_known_pois(
    registry: list[PoiReference],
    extra_pois: list[POI],
) -> dict[str, POI]:
    known: dict[str, POI] = {ref.poi_id: reference_to_poi(ref) for ref in registry}
    for poi in extra_pois:
        known[poi.osm_id] = poi
    return known


def _build_poi_registry(days: list[DayPlan], known_pois: dict[str, POI]) -> list[PoiReference]:
    scheduled_ids: list[str] = []
    seen: set[str] = set()
    for day in days:
        for activity in day.activities:
            if not activity.poi_id or activity.poi_id in seen:
                continue
            seen.add(activity.poi_id)
            scheduled_ids.append(activity.poi_id)

    scheduled_ids.sort()
    return [
        poi_to_reference(known_pois[poi_id])
        for poi_id in scheduled_ids
        if poi_id in known_pois
    ]
