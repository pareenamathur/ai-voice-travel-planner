"""Itinerary Builder — typed helpers for MCP tool inputs."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.mcp_servers.poi_search.models import POI
from src.shared.itinerary import Itinerary, PoiReference, TravelerConstraints


def poi_from_dict(data: dict[str, Any]) -> POI:
    """Parse a normalized POI dict into a ``POI`` model."""
    try:
        return POI.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid POI payload: {exc}") from exc


def pois_from_dicts(data: list[dict[str, Any]]) -> list[POI]:
    """Parse a list of POI dicts."""
    return [poi_from_dict(item) for item in data]


def itinerary_from_dict(data: dict[str, Any]) -> Itinerary:
    """Parse a canonical itinerary dict."""
    try:
        return Itinerary.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid itinerary payload: {exc}") from exc


def constraints_from_dict(data: dict[str, Any] | None) -> TravelerConstraints:
    """Parse traveler constraints; empty input yields defaults."""
    if not data:
        return TravelerConstraints()
    try:
        return TravelerConstraints.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid traveler_constraints payload: {exc}") from exc


def merge_constraints(
    base: TravelerConstraints,
    updates: TravelerConstraints | None,
) -> TravelerConstraints:
    """Merge partial constraint updates onto an existing constraint set."""
    if updates is None:
        return base
    patch = updates.model_dump(exclude_unset=True)
    if not patch:
        return base
    return base.model_copy(update=patch)


def poi_to_reference(poi: POI) -> PoiReference:
    """Convert a normalized POI to a registry reference."""
    return PoiReference(
        poi_id=poi.osm_id,
        name=poi.name,
        latitude=poi.lat,
        longitude=poi.lon,
        category=poi.category,
        source=poi.source,
    )


def reference_to_poi(ref: PoiReference) -> POI:
    """Convert a registry reference back to a normalized POI."""
    return POI(
        osm_id=ref.poi_id,
        name=ref.name,
        lat=ref.latitude,
        lon=ref.longitude,
        category=ref.category,
        source=ref.source,
    )
