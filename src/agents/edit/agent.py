"""Edit Agent — scoped patches via Gateway; returns EditArtifact to Review only (Phase 6)."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.agents.edit.intent import ParsedEditIntent, parse_edit_intent
from src.mcp_servers.itinerary_builder.models import reference_to_poi
from src.mcp_servers.itinerary_builder.scheduler import _order_day_pois
from src.mcp_servers.itinerary_builder.travel import estimate_travel_time
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
        },
        {
            "osm_id": "well_known/jaipur-lmb",
            "name": "Laxmi Misthan Bhandar (LMB)",
            "lat": 26.9190,
            "lon": 75.8265,
            "source": "well_known",
            "category": "food",
        },
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
    "culture": [
        {
            "osm_id": "well_known/jaipur-albert-hall",
            "name": "Albert Hall Museum",
            "lat": 26.9115,
            "lon": 75.8195,
            "source": "well_known",
            "category": "culture",
        }
    ],
}

_OUTDOOR_CATEGORIES = frozenset({"landmark", "sightseeing", "nature", "park"})


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

        rebuilt, scope_day = await self._apply_edit(
            itinerary=itinerary,
            before_snapshot=before_snapshot,
            parsed=parsed,
            day_number=day_number,
            city=str(itinerary.get("city") or task.payload.get("city") or ""),
            correlation_id=correlation_id,
        )

        scope = EditScope(
            day=scope_day,
            intent=parsed.raw_intent or parsed.action,
        )
        self._trace(
            "edit_artifact_created",
            correlation_id,
            action=parsed.action,
            day_number=scope_day,
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
    ) -> tuple[dict[str, Any], int]:
        assert self.gateway is not None

        if parsed.action == "move_location":
            updated = await self._apply_move(
                itinerary=itinerary,
                before_snapshot=before_snapshot,
                target_name=parsed.target_name,
                dest_day=day_number,
                correlation_id=correlation_id,
            )
            return updated, day_number

        model = Itinerary.model_validate(itinerary)
        registry = {ref.poi_id: ref for ref in model.poi_registry}

        # When the user names a place without a day, edit the day that contains it.
        if parsed.action in {"replace_location", "remove_location"} and parsed.day_number is None:
            found_day, _ = _find_named_poi_day(model, registry, parsed.target_name)
            if found_day is not None:
                day_number = found_day

        day = _get_day(model, day_number)
        day_pois = _pois_for_day(day, registry)

        traveler_constraints = model.traveler_constraints.model_dump(mode="json")
        replacement_pois = list(day_pois)

        if parsed.action == "relax_day":
            traveler_constraints = {**traveler_constraints, "pace": "relaxed"}
            replacement_pois = _thin_day_for_relax(day_pois)
        elif parsed.action == "replace_category":
            replacement_pois = _replace_category_pois(
                day_pois,
                from_category=parsed.target_category,
                to_category=parsed.replacement_category,
                city=city,
            )
        elif parsed.action in {"add_cafe", "add_food"}:
            food = _extra_pois("food", city)[:1]
            replacement_pois = _append_unique_pois(day_pois, food)
        elif parsed.action == "add_adventure":
            replacement_pois = _append_unique_pois(day_pois, _extra_pois("landmark", city))
        elif parsed.action == "remove_location":
            replacement_pois = _remove_named_poi(day_pois, parsed.target_name)
        elif parsed.action == "replace_location":
            replacement_pois = _replace_named_poi(
                day_pois,
                target_name=parsed.target_name,
                replacement_name=parsed.replacement_name,
                city=city,
            )
        elif parsed.action == "change_lunch":
            replacement_pois = _change_lunch_poi(day_pois, city=city)
        elif parsed.action == "food_tour":
            replacement_pois = _food_tour_pois(city=city)
            traveler_constraints = {**traveler_constraints, "interests": ["food"]}
        elif parsed.action == "replace_day_city":
            replacement_pois = _pois_for_city_day(parsed.target_name or city)
            if replacement_pois:
                city = str(parsed.target_name or city)
        elif parsed.action == "luxury_pace":
            traveler_constraints = {
                **traveler_constraints,
                "pace": "relaxed",
                "budget": "high",
            }
        elif parsed.action == "outdoors_day":
            traveler_constraints = {
                **traveler_constraints,
                "pace": "moderate",
                "interests": ["nature"],
            }
            replacement_pois = _append_unique_pois(day_pois, _extra_pois("landmark", city))
        elif parsed.action == "reduce_travel":
            if parsed.day_number is None:
                updated = await self._apply_reduce_travel_all(
                    itinerary=itinerary,
                    before_snapshot=before_snapshot,
                    traveler_constraints=traveler_constraints,
                    correlation_id=correlation_id,
                )
                return updated, day_number
            replacement_pois = _optimize_travel_order(day_pois)
        elif parsed.action == "make_indoors":
            replacement_pois = _swap_outdoor_for_indoor(day_pois, city=city)
        else:
            if parsed.action == "generic" and "relax" in parsed.raw_intent.lower():
                traveler_constraints = {**traveler_constraints, "pace": "relaxed"}
                replacement_pois = _thin_day_for_relax(day_pois)

        updated = await self._rebuild_day(
            itinerary=itinerary,
            day_number=day_number,
            pois=replacement_pois,
            traveler_constraints=traveler_constraints,
            correlation_id=correlation_id,
            action=parsed.action,
        )
        _assert_unchanged_days(before_snapshot, updated, edited_day=day_number)
        return updated, day_number

    async def _apply_move(
        self,
        *,
        itinerary: dict[str, Any],
        before_snapshot: dict[str, Any],
        target_name: str | None,
        dest_day: int,
        correlation_id: str,
    ) -> dict[str, Any]:
        model = Itinerary.model_validate(itinerary)
        registry = {ref.poi_id: ref for ref in model.poi_registry}
        source_day_number, moving = _find_named_poi_day(model, registry, target_name)
        if moving is None or source_day_number is None:
            raise ValueError(f"Could not find '{target_name}' in the itinerary to move")

        if source_day_number == dest_day:
            return dict(itinerary)

        source_day = _get_day(model, source_day_number)
        dest = _get_day(model, dest_day)
        source_pois = [p for p in _pois_for_day(source_day, registry) if p.osm_id != moving.osm_id]
        dest_pois = _append_unique_pois(_pois_for_day(dest, registry), [moving])
        constraints = model.traveler_constraints.model_dump(mode="json")

        updated = await self._rebuild_day(
            itinerary=itinerary,
            day_number=source_day_number,
            pois=source_pois,
            traveler_constraints=constraints,
            correlation_id=correlation_id,
            action="move_location",
        )
        updated = await self._rebuild_day(
            itinerary=updated,
            day_number=dest_day,
            pois=dest_pois,
            traveler_constraints=constraints,
            correlation_id=correlation_id,
            action="move_location",
        )
        _assert_unchanged_except(before_snapshot, updated, {source_day_number, dest_day})
        return updated

    async def _apply_reduce_travel_all(
        self,
        *,
        itinerary: dict[str, Any],
        before_snapshot: dict[str, Any],
        traveler_constraints: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        model = Itinerary.model_validate(itinerary)
        registry = {ref.poi_id: ref for ref in model.poi_registry}
        updated = itinerary
        touched: set[int] = set()
        for day in model.days:
            day_pois = _pois_for_day(day, registry)
            optimized = _optimize_travel_order(day_pois)
            if [p.osm_id for p in optimized] != [p.osm_id for p in day_pois]:
                touched.add(day.day_number)
                updated = await self._rebuild_day(
                    itinerary=updated,
                    day_number=day.day_number,
                    pois=optimized,
                    traveler_constraints=traveler_constraints,
                    correlation_id=correlation_id,
                    action="reduce_travel",
                )
        if not touched:
            # Still rebuild day 1 so Review sees a scoped edit attempt with same POIs reordered.
            day1 = model.days[0].day_number if model.days else 1
            updated = await self._rebuild_day(
                itinerary=updated,
                day_number=day1,
                pois=_optimize_travel_order(_pois_for_day(_get_day(model, day1), registry)),
                traveler_constraints=traveler_constraints,
                correlation_id=correlation_id,
                action="reduce_travel",
            )
            touched.add(day1)
        _assert_unchanged_except(before_snapshot, updated, touched)
        return updated

    async def _rebuild_day(
        self,
        *,
        itinerary: dict[str, Any],
        day_number: int,
        pois: list[POI],
        traveler_constraints: dict[str, Any],
        correlation_id: str,
        action: str,
    ) -> dict[str, Any]:
        assert self.gateway is not None
        self._trace(
            "rebuild_day",
            correlation_id,
            day_number=day_number,
            action=action,
            poi_count=len(pois),
        )
        result = await self.gateway.invoke(
            AgentRole.EDIT,
            "rebuild_day",
            {
                "itinerary": itinerary,
                "day_number": day_number,
                "pois": [poi.model_dump() for poi in pois],
                "traveler_constraints": traveler_constraints,
            },
            correlation_id=correlation_id,
        )
        if not isinstance(result, dict) or "itinerary" not in result:
            raise ValueError("rebuild_day must return an itinerary payload")
        return dict(result["itinerary"])


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
        category = str(activity.category or "").lower()
        # Skip scheduler-injected meal/rest slots that are not real POIs.
        if category in {"rest", "food"} and not activity.poi_id:
            continue
        if activity.poi_id and activity.poi_id in registry:
            pois.append(reference_to_poi(registry[activity.poi_id]))
            continue
        if activity.poi_id and activity.latitude is not None and activity.longitude is not None:
            pois.append(
                POI(
                    osm_id=activity.poi_id,
                    name=activity.title,
                    lat=activity.latitude,
                    lon=activity.longitude,
                    category=str(activity.category) if activity.category is not None else None,
                )
            )
            continue
        if (
            activity.poi_id is None
            and activity.latitude is not None
            and activity.longitude is not None
            and category not in {"rest", "food"}
        ):
            pois.append(
                POI(
                    osm_id=activity.id,
                    name=activity.title,
                    lat=activity.latitude,
                    lon=activity.longitude,
                    category=str(activity.category) if activity.category is not None else None,
                )
            )
    return pois


def _find_named_poi_day(
    itinerary: Itinerary,
    registry: dict[str, PoiReference],
    target_name: str | None,
) -> tuple[int | None, POI | None]:
    if not target_name:
        return None, None
    needle = target_name.lower()
    for day in itinerary.days:
        for poi in _pois_for_day(day, registry):
            if needle in poi.name.lower():
                return day.day_number, poi
    return None, None


def _thin_day_for_relax(day_pois: list[POI]) -> list[POI]:
    """Drop the last stop when a day has multiple stops so relaxed pace is visible."""
    if len(day_pois) <= 1:
        return list(day_pois)
    return list(day_pois[:-1])


def _optimize_travel_order(day_pois: list[POI]) -> list[POI]:
    """Try each POI as tour start; keep the lowest total travel path."""
    if len(day_pois) <= 2:
        return _order_day_pois(day_pois)

    best = list(day_pois)
    best_cost = _path_travel_cost(best)
    for start_index in range(len(day_pois)):
        rotated = day_pois[start_index:] + day_pois[:start_index]
        ordered = _order_day_pois(rotated)
        cost = _path_travel_cost(ordered)
        if cost < best_cost:
            best = ordered
            best_cost = cost
    return best


def _path_travel_cost(pois: list[POI]) -> int:
    if len(pois) < 2:
        return 0
    return sum(estimate_travel_time(pois[i], pois[i + 1]) for i in range(len(pois) - 1))


def _swap_outdoor_for_indoor(day_pois: list[POI], *, city: str) -> list[POI]:
    indoors = _extra_pois("culture", city)
    if not indoors:
        indoors = [
            POI.model_validate(item)
            for item in well_known_pois_for_city(city, interests=["culture"])
            if (item.get("category") or "").lower() == "culture"
        ]
    if not indoors:
        return day_pois

    result: list[POI] = []
    replaced = False
    for poi in day_pois:
        category = (poi.category or "").lower()
        if not replaced and category in _OUTDOOR_CATEGORIES:
            candidate = next((p for p in indoors if p.osm_id != poi.osm_id), indoors[0])
            result.append(candidate)
            replaced = True
        else:
            result.append(poi)
    if not replaced and indoors:
        result = _append_unique_pois(result[:-1] if result else result, indoors[:1]) or result
    return result


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


def _replace_named_poi(
    day_pois: list[POI],
    *,
    target_name: str | None,
    replacement_name: str | None,
    city: str,
) -> list[POI]:
    without = _remove_named_poi(day_pois, target_name)
    if replacement_name:
        candidates = [
            POI.model_validate(item)
            for item in well_known_pois_for_city(city, interests=None)
            if replacement_name.lower() in str(item.get("name") or "").lower()
        ]
        if candidates:
            return _append_unique_pois(without, candidates[:1])
    # Default: swap for a different landmark/culture not already scheduled.
    existing_ids = {p.osm_id for p in without}
    for category in ("landmark", "culture"):
        for poi in _extra_pois(category, city):
            if poi.osm_id not in existing_ids:
                return _append_unique_pois(without, [poi])
        for item in well_known_pois_for_city(city, interests=[category]):
            if item.get("osm_id") not in existing_ids:
                return _append_unique_pois(without, [POI.model_validate(item)])
    return without


def _change_lunch_poi(day_pois: list[POI], *, city: str) -> list[POI]:
    without_food = [poi for poi in day_pois if (poi.category or "").lower() != "food"]
    lunch_options = _extra_pois("food", city)
    if not lunch_options:
        return day_pois
    return _append_unique_pois(without_food, lunch_options[:1])


def _food_tour_pois(*, city: str) -> list[POI]:
    food = _extra_pois("food", city)
    if len(food) < 3:
        food = food + _extra_pois("food", city)
    fallback = [
        POI.model_validate(item)
        for item in well_known_pois_for_city(city, interests=["food"])
        if (item.get("category") or "").lower() == "food"
    ]
    return _append_unique_pois(food, fallback)[:5]


def _pois_for_city_day(city: str) -> list[POI]:
    normalized = city.strip().title()
    candidates = [
        POI.model_validate(item)
        for item in well_known_pois_for_city(normalized, interests=["landmark", "culture"])
    ]
    if candidates:
        return candidates[:4]
    return [
        POI.model_validate(item)
        for item in well_known_pois_for_city(normalized, interests=["landmark"])
    ][:4]


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
    _assert_unchanged_except(before, after, {edited_day})


def _assert_unchanged_except(
    before: dict[str, Any],
    after: dict[str, Any],
    edited_days: set[int],
) -> None:
    before_days = {day["day_number"]: day for day in before.get("days") or []}
    after_days = {day["day_number"]: day for day in after.get("days") or []}
    for day_number, day in before_days.items():
        if day_number in edited_days:
            continue
        if after_days.get(day_number) != day:
            raise ValueError(f"day {day_number} changed during scoped edit")
