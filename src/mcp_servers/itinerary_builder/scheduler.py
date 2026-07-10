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
)

DEFAULT_DAY_START = "09:00"
DEFAULT_SIGHTSEEING_END = "18:00"
MIN_DAY_MINUTES = 480
MAX_DAY_MINUTES = 600
DEFAULT_ACTIVITY_MINUTES = 90
NEARBY_GROUP_RADIUS_KM = 2.0


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    day_start: str = DEFAULT_DAY_START
    sightseeing_end: str = DEFAULT_SIGHTSEEING_END
    min_day_minutes: int = MIN_DAY_MINUTES
    max_day_minutes: int = MAX_DAY_MINUTES
    default_activity_minutes: int = DEFAULT_ACTIVITY_MINUTES
    nearby_radius_km: float = NEARBY_GROUP_RADIUS_KM


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
    """Schedule one day of activities with travel segments."""
    resolved = config or SchedulerConfig()
    day_start = constraints.daily_window_start or resolved.day_start
    sightseeing_end = _time_to_minutes(constraints.daily_window_end or resolved.sightseeing_end)

    current_minute = _time_to_minutes(day_start)
    day_elapsed = 0
    activities: list[Activity] = []
    travel_segments: list[TravelSegment] = []

    ordered_pois = _order_day_pois(pois)
    previous_poi: POI | None = None

    for index, poi in enumerate(ordered_pois, start=1):
        if day_elapsed >= resolved.max_day_minutes:
            break

        if previous_poi is not None:
            travel_minutes = estimate_travel_time(previous_poi, poi)
            distance_km = haversine_distance_km(
                previous_poi.lat, previous_poi.lon, poi.lat, poi.lon
            )
            mode = infer_transport_mode(distance_km)

            if day_elapsed + travel_minutes > resolved.max_day_minutes:
                break

            current_minute += travel_minutes
            day_elapsed += travel_minutes
            travel_segments.append(
                TravelSegment(
                    from_activity_id=activities[-1].id,
                    to_activity_id=f"d{day_number}-a{index}",
                    travel_minutes=travel_minutes,
                    transport_mode=mode,
                )
            )

        duration = _activity_duration_minutes(poi, constraints, resolved)
        if current_minute > sightseeing_end:
            break
        if day_elapsed + duration > resolved.max_day_minutes:
            duration = max(resolved.max_day_minutes - day_elapsed, 0)
            if duration == 0:
                break

        start_time = _minutes_to_time(current_minute)
        end_minute = current_minute + duration
        activities.append(
            Activity(
                id=f"d{day_number}-a{index}",
                title=poi.name,
                poi_id=poi.osm_id,
                category=poi.category,
                latitude=poi.lat,
                longitude=poi.lon,
                start_time=start_time,
                end_time=_minutes_to_time(end_minute),
                duration_minutes=duration,
            )
        )
        current_minute = end_minute
        day_elapsed += duration
        previous_poi = poi

    return DayPlan(
        day_number=day_number,
        date=plan_date,
        activities=activities,
        travel_segments=travel_segments,
    )


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
