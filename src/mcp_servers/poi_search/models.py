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


def infer_category_from_tags(tags: dict[str, Any]) -> str | None:
    """Best-effort POI category from OSM tags."""
    amenity = str(tags.get("amenity") or "").lower()
    tourism = str(tags.get("tourism") or "").lower()
    leisure = str(tags.get("leisure") or "").lower()
    shop = tags.get("shop")
    natural = tags.get("natural")
    sport = tags.get("sport")
    historic = tags.get("historic")

    if amenity in {"restaurant", "cafe", "fast_food", "food_court", "biergarten"}:
        return "food"
    if amenity in {"bar", "pub", "nightclub"}:
        return "nightlife"
    if tourism in {"museum", "gallery", "artwork"} or amenity == "theatre":
        return "culture"
    if shop is not None or amenity == "marketplace":
        return "shopping"
    if leisure in {"park", "nature_reserve", "playground"} or natural:
        return "nature"
    if leisure in {"sports_centre", "track"} or sport:
        return "adventure"
    if tourism in {"zoo", "theme_park", "aquarium"}:
        return "family"
    if tourism in {"theme_park"} or (
        tourism == "attraction"
        and any(
            token in str(tags.get("attraction") or "").lower()
            for token in ("hiking", "climbing", "adventure", "safari", "zip", "trek")
        )
    ):
        return "adventure"
    if historic or tourism in {"attraction", "viewpoint"}:
        return "landmark"
    return None


def osm_element_to_poi(element: dict[str, Any], *, category: str | None = None) -> POI | None:
    """Convert an Overpass `element` to a normalized POI.

    Overpass can return nodes (lat/lon at top-level) and ways/relations (center.lat/lon).
    """

    el_type = element.get("type")
    el_id = element.get("id")
    if not el_type or el_id is None:
        return None

    tags = element.get("tags") or {}
    name = tags.get("name") or tags.get("name:en") or tags.get("alt_name")
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

    resolved_category = category or infer_category_from_tags(tags)

    return POI(
        osm_id=f"{el_type}/{el_id}",
        name=str(name),
        lat=float(lat),
        lon=float(lon),
        source="osm",
        category=resolved_category,
        tags=dict(tags),
    )

