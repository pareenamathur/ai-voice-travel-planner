"""Edit Agent — scoped patches via Gateway; returns EditArtifact to Review only (Phase 6)."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.agents.edit.intent import ParsedEditIntent, parse_edit_intent
from src.mcp_servers.itinerary_builder.models import reference_to_poi
from src.mcp_servers.poi_search.fallback import well_known_pois_for_city
from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import Itinerary, PoiReference
from src.shared.messages.types import (
    AgentRole,
    EditArtifact,
    EditScope,
    TaskMessage,
    TaskType,
)

_EXTRA_POIS_BY_CATEGORY: dict[str, list[dict[str, Any]]] = {
    "food": [
        {
            "osm_id": "well_known/jaipur-indian-coffee-house",
            "name": "Indian Coffee House",
            "lat": 26.9152,
            "lon": 75.8189,
            "source": "well_known",
            "category": "food",
        }
    ],
    "shopping": [
        {
            "osm_id": "well_known/jaipur-johari-bazaar",
            "name": "Johari Bazaar",
            "lat": 26.9260,
            "lon": 75.8230,
            "source": "well_known",
            "category": "shopping",
        }
    ],
    "landmark": [
        {
            "osm_id": "well_known/jaipur-nahargarh-fort",
            "name": "Nahargarh Fort",
            "lat": 26.9376,
            "lon": 75.8155,
            "source": "well_known",
            "category": "landmark",
        }
    ],
}


class EditAgent(BaseAgent):
    """Invokes ``rebuild_day`` via Gateway. Never user-facing."""

    role = AgentRole.EDIT

    async def run(self, task: TaskMessage) -> EditArtifact:
        if task.task_type != TaskType.EDIT:
            raise ValueError(f"Edit Agent requires task_type=EDIT, got '{task.task_type}'")

        correlation_id = task.correlation_id
        self._trace("delegation_started", correlation_id, task_type=task.task_type.value)

        itinerary = dict(task.payload.get("itinerary") or {})
        if not itinerary:
            raise ValueError("EDIT payload.itinerary is required")

        before_snapshot = dict(task.payload.get("before_snapshot") or itinerary)
        message = str(task.payload.get("edit_intent") or task.payload.get("message") or "")
        parsed = parse_edit_intent(message) or ParsedEditIntent(action="generic", raw_intent=message)

        day_number = parsed.day_number or _default_day_number(itinerary)
        if day_number is None:
            raise ValueError("Could not determine which day to edit")

        rebuilt = await self._apply_edit(
            itinerary=itinerary,
            before_snapshot=before_snapshot,
            parsed=parsed,
            day_number=day_number,
            city=str(itinerary.get("city") or task.payload.get("city") or ""),
            correlation_id=correlation_id,
        )

        scope = EditScope(
            day=day_number,
            intent=parsed.raw_intent or parsed.action,
        )
        self._trace(
            "edit_artifact_created",
            correlation_id,
            action=parsed.action,
            day_number=day_number,
        )
        return EditArtifact(
            itinerary=rebuilt,
            edit_scope=scope,
            before_snapshot=before_snapshot,
            correlation_id=correlation_id,
        )

    async def handle_regen(self, hints: dict[str, Any], correlation_id: str) -> EditArtifact:
        self._trace("regen_requested", correlation_id, hints=hints)
        return EditArtifact(
            itinerary=dict(hints.get("itinerary") or {}),
            edit_scope=EditScope(intent="regen"),
            before_snapshot=dict(hints.get("before_snapshot") or {}),
            correlation_id=correlation_id,
        )

    async def _apply_edit(
        self,
        *,
        itinerary: dict[str, Any],
        before_snapshot: dict[str, Any],
        parsed: ParsedEditIntent,
        day_number: int,
        city: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        assert self.gateway is not None

        model = Itinerary.model_validate(itinerary)
        registry = {ref.poi_id: ref for ref in model.poi_registry}
        day = _get_day(model, day_number)
        day_pois = _pois_for_day(day, registry)

        traveler_constraints = model.traveler_constraints.model_dump(mode="json")
        replacement_pois = list(day_pois)

        if parsed.action == "relax_day":
            traveler_constraints = {**traveler_constraints, "pace": "relaxed"}
        elif parsed.action == "replace_category":
            replacement_pois = _replace_category_pois(
                day_pois,
                from_category=parsed.target_category,
                to_category=parsed.replacement_category,
                city=city,
            )
        elif parsed.action == "add_cafe":
            replacement_pois = _append_unique_pois(day_pois, _extra_pois("food", city))
        elif parsed.action == "add_adventure":
            replacement_pois = _append_unique_pois(day_pois, _extra_pois("landmark", city))
        elif parsed.action == "remove_location":
            replacement_pois = _remove_named_poi(day_pois, parsed.target_name)
        elif parsed.action == "change_lunch":
            replacement_pois = _change_lunch_poi(day_pois, city=city)
        else:
            if parsed.action == "generic" and "relax" in parsed.raw_intent.lower():
                traveler_constraints = {**traveler_constraints, "pace": "relaxed"}

        self._trace(
            "rebuild_day",
            correlation_id,
            day_number=day_number,
            action=parsed.action,
            poi_count=len(replacement_pois),
        )
        result = await self.gateway.invoke(
            AgentRole.EDIT,
            "rebuild_day",
            {
                "itinerary": itinerary,
                "day_number": day_number,
                "pois": [poi.model_dump() for poi in replacement_pois],
                "traveler_constraints": traveler_constraints,
            },
            correlation_id=correlation_id,
        )
        if not isinstance(result, dict) or "itinerary" not in result:
            raise ValueError("rebuild_day must return an itinerary payload")

        updated = dict(result["itinerary"])
        _assert_unchanged_days(before_snapshot, updated, edited_day=day_number)
        return updated


def _default_day_number(itinerary: dict[str, Any]) -> int | None:
    days = itinerary.get("days") or []
    if not days:
        return None
    return int(days[0].get("day_number", 1))


def _get_day(itinerary: Itinerary, day_number: int):
    for day in itinerary.days:
        if day.day_number == day_number:
            return day
    raise ValueError(f"day_number {day_number} not found in itinerary")


def _pois_for_day(day, registry: dict[str, PoiReference]) -> list[POI]:
    pois: list[POI] = []
    for activity in day.activities:
        if activity.poi_id and activity.poi_id in registry:
            pois.append(reference_to_poi(registry[activity.poi_id]))
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


def _replace_category_pois(
    day_pois: list[POI],
    *,
    from_category: str | None,
    to_category: str | None,
    city: str,
) -> list[POI]:
    kept = [
        poi
        for poi in day_pois
        if not from_category or (poi.category or "").lower() != from_category.lower()
    ]
    candidates = [
        POI.model_validate(item)
        for item in well_known_pois_for_city(city, interests=[to_category or "shopping"])
        if (to_category is None or (item.get("category") or "").lower() == to_category.lower())
    ]
    return _append_unique_pois(kept, candidates)


def _append_unique_pois(existing: list[POI], extras: list[POI]) -> list[POI]:
    seen = {poi.osm_id for poi in existing}
    merged = list(existing)
    for poi in extras:
        if poi.osm_id in seen:
            continue
        seen.add(poi.osm_id)
        merged.append(poi)
    return merged


def _remove_named_poi(day_pois: list[POI], target_name: str | None) -> list[POI]:
    if not target_name:
        return day_pois
    needle = target_name.lower()
    return [poi for poi in day_pois if needle not in poi.name.lower()]


def _change_lunch_poi(day_pois: list[POI], *, city: str) -> list[POI]:
    without_food = [poi for poi in day_pois if (poi.category or "").lower() != "food"]
    lunch_options = _extra_pois("food", city)
    if not lunch_options:
        return day_pois
    return _append_unique_pois(without_food, lunch_options[:1])


def _extra_pois(category: str, city: str) -> list[POI]:
    extras = [POI.model_validate(item) for item in _EXTRA_POIS_BY_CATEGORY.get(category, [])]
    if extras:
        return extras
    return [
        POI.model_validate(item)
        for item in well_known_pois_for_city(city, interests=[category])
        if (item.get("category") or "").lower() == category
    ]


def _assert_unchanged_days(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    edited_day: int,
) -> None:
    before_days = {day["day_number"]: day for day in before.get("days") or []}
    after_days = {day["day_number"]: day for day in after.get("days") or []}
    for day_number, day in before_days.items():
        if day_number == edited_day:
            continue
        if after_days.get(day_number) != day:
            raise ValueError(f"day {day_number} changed during scoped edit")
