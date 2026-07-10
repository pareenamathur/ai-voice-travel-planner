"""Travel time estimation for itinerary scheduling (Phase 3 Task 2)."""

from __future__ import annotations

import math

from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import TransportMode

EARTH_RADIUS_KM = 6371.0
DEFAULT_WALK_SPEED_KMH = 4.5
DEFAULT_DRIVE_SPEED_KMH = 25.0
MAX_TRAVEL_MINUTES = 45
WALK_DISTANCE_THRESHOLD_KM = 1.5


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _speed_kmh_for_mode(transport_mode: TransportMode | str) -> float:
    mode = str(transport_mode).lower()
    if mode == TransportMode.WALK:
        return DEFAULT_WALK_SPEED_KMH
    return DEFAULT_DRIVE_SPEED_KMH


def infer_transport_mode(distance_km: float) -> TransportMode:
    """Pick a simple transport mode from straight-line distance."""
    if distance_km <= WALK_DISTANCE_THRESHOLD_KM:
        return TransportMode.WALK
    return TransportMode.DRIVE


def estimate_travel_time(
    origin: POI,
    destination: POI,
    *,
    transport_mode: TransportMode | str | None = None,
) -> int:
    """Estimate travel minutes between two POIs using Haversine distance."""
    distance_km = haversine_distance_km(origin.lat, origin.lon, destination.lat, destination.lon)
    mode = transport_mode or infer_transport_mode(distance_km)
    speed_kmh = _speed_kmh_for_mode(mode)
    if speed_kmh <= 0:
        return 0

    minutes = math.ceil((distance_km / speed_kmh) * 60)
    return int(min(max(minutes, 0), MAX_TRAVEL_MINUTES))
