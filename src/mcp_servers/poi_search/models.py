"""POI Search — typed models and normalization helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class POI(BaseModel):
    """Normalized POI returned from `search_pois`."""

    osm_id: str = Field(..., examples=["node/123", "way/456", "relation/789"])
    name: str = Field(..., min_length=1)
    lat: float
    lon: float
    source: str = Field(default="osm", examples=["osm"])

    category: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)


def osm_element_to_poi(element: dict[str, Any], *, category: str | None = None) -> POI | None:
    """Convert an Overpass `element` to a normalized POI.

    Overpass can return nodes (lat/lon at top-level) and ways/relations (center.lat/lon).
    """

    el_type = element.get("type")
    el_id = element.get("id")
    if not el_type or el_id is None:
        return None

    tags = element.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None

    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    return POI(
        osm_id=f"{el_type}/{el_id}",
        name=str(name),
        lat=float(lat),
        lon=float(lon),
        source="osm",
        category=category,
        tags=dict(tags),
    )

