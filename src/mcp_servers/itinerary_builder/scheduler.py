"""Deterministic itinerary scheduling heuristic (Phase 3 Task 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta

from src.mcp_servers.itinerary_builder.travel import (
    estimate_travel_time,
    haversine_distance_km,
    infer_transport_mode,
)
from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import (
    Activity,
    DayPlan,
    Itinerary,
    PoiReference,
    TravelerConstraints,
    TravelSegment,
    TransportMode,
)

DEFAULT_DAY_START = "09:00"
DEFAULT_SIGHTSEEING_END = "21:00"
MIN_DAY_MINUTES = 480
MAX_DAY_MINUTES = 720
DEFAULT_ACTIVITY_MINUTES = 90
NEARBY_GROUP_RADIUS_KM = 2.0
LUNCH_WINDOW_START = 12 * 60 + 15  # 12:15
LUNCH_DURATION = 60
TEA_WINDOW_START = 16 * 60  # 16:00
TEA_DURATION = 30
DINNER_WINDOW_START = 19 * 60  # 19:00
DINNER_DURATION = 60
EVENING_RETURN_MINUTE = 21 * 60  # 21:00
RETURN_DURATION = 20
EVENING_WINDOW_START = 17 * 60 + 30  # 17:30 — prefer a real stop before dinner
EVENING_ACTIVITY_MINUTES = 75

# Categories that naturally suit late afternoon / evening (markets, walks, parks).
_EVENING_FRIENDLY_CATEGORIES = frozenset(
    {
        "shopping",
        "nature",
        "park",
        "viewpoint",
        "nightlife",
        "market",
        "sightseeing",
    }
)


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    day_start: str = DEFAULT_DAY_START
    sightseeing_end: str = DEFAULT_SIGHTSEEING_END
    min_day_minutes: int = MIN_DAY_MINUTES
    max_day_minutes: int = MAX_DAY_MINUTES
    default_activity_minutes: int = DEFAULT_ACTIVITY_MINUTES
    nearby_radius_km: float = NEARBY_GROUP_RADIUS_KM
    lunch_window_start: int = LUNCH_WINDOW_START
    lunch_duration: int = LUNCH_DURATION
    tea_window_start: int = TEA_WINDOW_START
    tea_duration: int = TEA_DURATION
    dinner_window_start: int = DINNER_WINDOW_START
    dinner_duration: int = DINNER_DURATION
    evening_return_minute: int = EVENING_RETURN_MINUTE
    return_duration: int = RETURN_DURATION
    evening_window_start: int = EVENING_WINDOW_START
    evening_activity_minutes: int = EVENING_ACTIVITY_MINUTES


def _time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _minutes_to_time(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _activity_duration_minutes(
    poi: POI,
    constraints: TravelerConstraints,
    config: SchedulerConfig,
) -> int:
    pace = (constraints.pace or "moderate").lower()
    if pace == "relaxed":
        base = int(config.default_activity_minutes * 1.33)
    elif pace in {"fast", "packed"}:
        base = int(config.default_activity_minutes * 0.75)
    else:
        base = config.default_activity_minutes

    if poi.category and poi.category.lower() == "food":
        return max(45, int(base * 0.75))
    return base


def _poi_reference(poi: POI) -> PoiReference:
    return PoiReference(
        poi_id=poi.osm_id,
        name=poi.name,
        latitude=poi.lat,
        longitude=poi.lon,
        category=poi.category,
        source=poi.source,
    )


def _deduplicate_pois(pois: list[POI]) -> list[POI]:
    seen: set[str] = set()
    unique: list[POI] = []
    for poi in pois:
        if poi.osm_id in seen:
            continue
        seen.add(poi.osm_id)
        unique.append(poi)
    return unique


def group_nearby_pois(
    pois: list[POI],
    *,
    radius_km: float = NEARBY_GROUP_RADIUS_KM,
) -> list[list[POI]]:
    """Greedy geographic clustering to keep nearby POIs together."""
    remaining = list(pois)
    clusters: list[list[POI]] = []

    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]
        kept: list[POI] = []

        for candidate in remaining:
            distance = haversine_distance_km(seed.lat, seed.lon, candidate.lat, candidate.lon)
            if distance <= radius_km:
                cluster.append(candidate)
            else:
                kept.append(candidate)

        remaining = kept
        clusters.append(cluster)

    clusters.sort(key=len, reverse=True)
    return clusters


def _order_day_pois(pois: list[POI]) -> list[POI]:
    """Nearest-neighbour ordering to reduce within-day travel."""
    if len(pois) <= 1:
        return list(pois)

    remaining = list(pois)
    ordered: list[POI] = [remaining.pop(0)]
    while remaining:
        current = ordered[-1]
        next_index = min(
            range(len(remaining)),
            key=lambda index: estimate_travel_time(current, remaining[index]),
        )
        ordered.append(remaining.pop(next_index))
    return ordered


def _distribute_pois_to_days(pois: list[POI], total_days: int) -> list[list[POI]]:
    """Balance POI counts across days while preserving rough geographic ordering."""
    clusters = group_nearby_pois(pois)
    ordered: list[POI] = []
    for cluster in clusters:
        ordered.extend(_order_day_pois(cluster))

    day_buckets: list[list[POI]] = [[] for _ in range(total_days)]
    for index, poi in enumerate(ordered):
        day_buckets[index % total_days].append(poi)

    return day_buckets


def schedule_day(
    *,
    day_number: int,
    pois: list[POI],
    constraints: TravelerConstraints,
    config: SchedulerConfig | None = None,
    plan_date: Date | None = None,
) -> DayPlan:
    """Schedule one full travel day: sightseeing, meals, evening wrap-up."""
    resolved = config or SchedulerConfig()
    day_start = constraints.daily_window_start or resolved.day_start
    sightseeing_end = _time_to_minutes(constraints.daily_window_end or resolved.sightseeing_end)

    current_minute = _time_to_minutes(day_start)
    day_elapsed = 0
    activities: list[Activity] = []
    travel_segments: list[TravelSegment] = []
    activity_index = 0

    ordered_pois = _order_day_pois(pois)
    food_pois = [p for p in ordered_pois if (p.category or "").lower() == "food"]
    sight_pois = [p for p in ordered_pois if (p.category or "").lower() != "food"]
    day_pois, evening_pois = _split_day_and_evening_pois(sight_pois)
    previous_poi: POI | None = None
    lunch_added = False
    tea_added = False
    dinner_added = False
    evening_activity_added = False

    def _next_id() -> str:
        nonlocal activity_index
        activity_index += 1
        return f"d{day_number}-a{activity_index}"

    def _append_poi_activity(poi: POI, *, period_override: str | None = None) -> bool:
        nonlocal current_minute, day_elapsed, previous_poi
        if day_elapsed >= resolved.max_day_minutes:
            return False
        if current_minute > sightseeing_end:
            return False

        act_id = _next_id()
        if previous_poi is not None:
            travel_minutes = estimate_travel_time(previous_poi, poi)
            distance_km = haversine_distance_km(
                previous_poi.lat, previous_poi.lon, poi.lat, poi.lon
            )
            mode = infer_transport_mode(distance_km)

            if day_elapsed + travel_minutes > resolved.max_day_minutes:
                return False

            current_minute += travel_minutes
            day_elapsed += travel_minutes
            travel_segments.append(
                TravelSegment(
                    from_activity_id=activities[-1].id,
                    to_activity_id=act_id,
                    travel_minutes=travel_minutes,
                    transport_mode=mode,
                )
            )

        duration = _activity_duration_minutes(poi, constraints, resolved)
        if period_override:
            duration = min(duration, resolved.evening_activity_minutes)
        if current_minute > sightseeing_end:
            return False
        if day_elapsed + duration > resolved.max_day_minutes:
            duration = max(resolved.max_day_minutes - day_elapsed, 0)
            if duration == 0:
                return False

        start_time = _minutes_to_time(current_minute)
        end_minute = current_minute + duration
        activities.append(
            Activity(
                id=act_id,
                title=poi.name,
                poi_id=poi.osm_id,
                category=poi.category,
                latitude=poi.lat,
                longitude=poi.lon,
                start_time=start_time,
                end_time=_minutes_to_time(end_minute),
                duration_minutes=duration,
                notes=period_override or _period_note(current_minute),
            )
        )
        current_minute = end_minute
        day_elapsed += duration
        previous_poi = poi
        return True

    def _append_break(
        *,
        title: str,
        category: str,
        duration: int,
        notes: str,
        food_poi: POI | None = None,
    ) -> bool:
        nonlocal current_minute, day_elapsed, previous_poi
        if day_elapsed + duration > resolved.max_day_minutes:
            return False
        if current_minute + duration > sightseeing_end + 30:
            return False
        act_id = _next_id()
        if activities and previous_poi is not None and food_poi is not None:
            travel_minutes = estimate_travel_time(previous_poi, food_poi)
            distance_km = haversine_distance_km(
                previous_poi.lat, previous_poi.lon, food_poi.lat, food_poi.lon
            )
            mode = infer_transport_mode(distance_km)
            current_minute += travel_minutes
            day_elapsed += travel_minutes
            travel_segments.append(
                TravelSegment(
                    from_activity_id=activities[-1].id,
                    to_activity_id=act_id,
                    travel_minutes=travel_minutes,
                    transport_mode=mode,
                )
            )
        elif activities:
            # Soft transition into a scheduled break near the last stop.
            soft_travel = 10
            current_minute += soft_travel
            day_elapsed += soft_travel
            travel_segments.append(
                TravelSegment(
                    from_activity_id=activities[-1].id,
                    to_activity_id=act_id,
                    travel_minutes=soft_travel,
                    transport_mode=TransportMode.WALK,
                    notes="Short walk to nearby dining / break",
                )
            )

        start = current_minute
        end = start + duration
        activities.append(
            Activity(
                id=act_id,
                title=title if food_poi is None else food_poi.name,
                poi_id=food_poi.osm_id if food_poi else None,
                category=category,
                latitude=food_poi.lat if food_poi else (
                    previous_poi.lat if previous_poi else None
                ),
                longitude=food_poi.lon if food_poi else (
                    previous_poi.lon if previous_poi else None
                ),
                start_time=_minutes_to_time(start),
                end_time=_minutes_to_time(end),
                duration_minutes=duration,
                notes=notes,
            )
        )
        current_minute = end
        day_elapsed += duration
        if food_poi is not None:
            previous_poi = food_poi
        return True

    def _maybe_insert_meals() -> None:
        nonlocal lunch_added, tea_added, dinner_added
        if not lunch_added and current_minute >= resolved.lunch_window_start and activities:
            food = food_pois.pop(0) if food_pois else None
            lunch_added = _append_break(
                title="Lunch break",
                category="food",
                duration=resolved.lunch_duration,
                notes="Lunch",
                food_poi=food,
            )
        if (
            not tea_added
            and lunch_added
            and current_minute >= resolved.tea_window_start
            and activities
        ):
            tea_added = _append_break(
                title="Tea / short break",
                category="rest",
                duration=resolved.tea_duration,
                notes="Tea break",
            )
        # Dinner waits until evening activities have had a chance to schedule.

    def _schedule_evening_pois() -> None:
        nonlocal evening_activity_added, current_minute
        if evening_activity_added or not evening_pois or not activities:
            return
        if current_minute < resolved.evening_window_start:
            current_minute = resolved.evening_window_start
        for poi in evening_pois:
            if current_minute >= resolved.dinner_window_start:
                break
            if _append_poi_activity(poi, period_override="Evening"):
                evening_activity_added = True

    for poi in day_pois:
        _maybe_insert_meals()
        if day_elapsed >= resolved.max_day_minutes:
            break
        if current_minute > sightseeing_end:
            break
        # Leave room for an evening stop before dinner when we still have reserved POIs.
        if (
            evening_pois
            and not evening_activity_added
            and current_minute >= resolved.evening_window_start - 30
        ):
            break
        _append_poi_activity(poi)

    # Fill remaining day structure even when few POIs remain.
    _maybe_insert_meals()
    if not lunch_added and activities:
        # Ensure at least a lunch slot when the morning finished early.
        if current_minute < resolved.lunch_window_start:
            current_minute = resolved.lunch_window_start
        food = food_pois.pop(0) if food_pois else None
        lunch_added = _append_break(
            title="Lunch break",
            category="food",
            duration=resolved.lunch_duration,
            notes="Lunch",
            food_poi=food,
        )

    if not tea_added and lunch_added and activities:
        if current_minute < resolved.tea_window_start:
            current_minute = resolved.tea_window_start
        tea_added = _append_break(
            title="Tea / short break",
            category="rest",
            duration=resolved.tea_duration,
            notes="Tea break",
        )

    _schedule_evening_pois()

    if not dinner_added and activities and current_minute < resolved.dinner_window_start + 30:
        if current_minute < resolved.dinner_window_start:
            current_minute = max(current_minute, resolved.dinner_window_start)
        food = food_pois.pop(0) if food_pois else None
        dinner_added = _append_break(
            title="Dinner",
            category="food",
            duration=resolved.dinner_duration,
            notes="Dinner",
            food_poi=food,
        )

    if activities and current_minute < resolved.evening_return_minute + 60:
        if current_minute < resolved.evening_return_minute:
            current_minute = resolved.evening_return_minute
        _append_break(
            title="Return to hotel",
            category="rest",
            duration=resolved.return_duration,
            notes="Night — return / hotel",
        )

    notes = None
    if activities:
        first = activities[0].start_time or day_start
        last = activities[-1].end_time or _minutes_to_time(current_minute)
        notes = f"Full day timeline {first}–{last}"

    return DayPlan(
        day_number=day_number,
        date=plan_date,
        activities=activities,
        travel_segments=travel_segments,
        notes=notes,
    )


def _split_day_and_evening_pois(sight_pois: list[POI]) -> tuple[list[POI], list[POI]]:
    """Reserve 1–2 evening-friendly stops so dinner is not the only evening activity."""
    if len(sight_pois) <= 1:
        return list(sight_pois), []

    preferred = [
        p
        for p in sight_pois
        if (p.category or "").lower() in _EVENING_FRIENDLY_CATEGORIES
    ]

    evening: list[POI] = []
    if preferred:
        evening = preferred[-2:] if len(preferred) >= 2 and len(sight_pois) >= 4 else preferred[-1:]
        day = [p for p in sight_pois if p not in evening]
    else:
        # No category match — still keep the last stop for evening atmosphere.
        evening = [sight_pois[-1]]
        day = list(sight_pois[:-1])

    # Prefer leaving at least two daytime stops when possible.
    if len(day) < 2 and evening and len(sight_pois) >= 3:
        moved = evening.pop(0)
        day.append(moved)
    return day, evening


def _period_note(start_minute: int) -> str:
    if start_minute < 12 * 60:
        return "Morning"
    if start_minute < 14 * 60:
        return "Late morning / midday"
    if start_minute < 17 * 60:
        return "Afternoon"
    if start_minute < 19 * 60:
        return "Early evening"
    return "Evening"


def schedule_itinerary(
    *,
    city: str,
    pois: list[POI],
    traveler_constraints: TravelerConstraints | None = None,
    total_days: int,
    start_date: Date | None = None,
    config: SchedulerConfig | None = None,
) -> Itinerary:
    """Build a canonical itinerary from POIs and traveler constraints."""
    if total_days < 1:
        raise ValueError("total_days must be at least 1")

    resolved_config = config or SchedulerConfig()
    constraints = traveler_constraints or TravelerConstraints()
    unique_pois = _deduplicate_pois(pois)
    day_assignments = _distribute_pois_to_days(unique_pois, total_days)

    days: list[DayPlan] = []
    for day_index, day_pois in enumerate(day_assignments, start=1):
        plan_date = start_date + timedelta(days=day_index - 1) if start_date else None
        days.append(
            schedule_day(
                day_number=day_index,
                pois=day_pois,
                constraints=constraints,
                config=resolved_config,
                plan_date=plan_date,
            )
        )

    scheduled_ids = {
        activity.poi_id
        for day in days
        for activity in day.activities
        if activity.poi_id is not None
    }
    registry = [
        _poi_reference(poi) for poi in unique_pois if poi.osm_id in scheduled_ids
    ]

    return Itinerary(
        city=city,
        total_days=total_days,
        start_date=start_date,
        traveler_constraints=constraints,
        days=days,
        poi_registry=registry,
        metadata={"scheduler": "heuristic_v1"},
    )
