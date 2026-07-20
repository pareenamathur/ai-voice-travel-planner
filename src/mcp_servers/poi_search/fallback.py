"""Well-known / LLM fallback POIs when live Overpass lookup is unavailable."""

from __future__ import annotations

import json
import re
from typing import Any

from src.mcp_servers.poi_search.models import POI

# Stable synthetic ids so itinerary builder / registry stay consistent across runs.
WELL_KNOWN_BY_CITY: dict[str, list[POI]] = {
    "jaipur": [
        POI(
            osm_id="well_known/jaipur-city-palace",
            name="City Palace",
            lat=26.9258,
            lon=75.8236,
            source="well_known",
            category="culture",
        ),
        POI(
            osm_id="well_known/jaipur-hawa-mahal",
            name="Hawa Mahal",
            lat=26.9239,
            lon=75.8267,
            source="well_known",
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-amber-fort",
            name="Amber Fort",
            lat=26.9855,
            lon=75.8513,
            source="well_known",
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-jantar-mantar",
            name="Jantar Mantar",
            lat=26.9247,
            lon=75.8246,
            source="well_known",
            category="culture",
        ),
        POI(
            osm_id="well_known/jaipur-jal-mahal",
            name="Jal Mahal",
            lat=26.9535,
            lon=75.8463,
            source="well_known",
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-bapu-bazaar",
            name="Bapu Bazaar",
            lat=26.9170,
            lon=75.8205,
            source="well_known",
            category="shopping",
        ),
    ],
}


def well_known_pois_for_city(city: str, *, interests: list[str] | None = None) -> list[dict[str, Any]]:
    """Return curated attractions for a city, optionally filtered by interest category."""
    key = (city or "").strip().lower()
    pois = list(WELL_KNOWN_BY_CITY.get(key) or _generic_city_pois(city))
    interests_norm = [i.strip().lower() for i in (interests or []) if i and i.strip()]
    if interests_norm:
        matched = [
            p
            for p in pois
            if p.category and p.category.lower() in interests_norm
        ]
        if matched:
            pois = matched + [p for p in pois if p not in matched]
    return [p.model_dump() for p in pois]


def _generic_city_pois(city: str) -> list[POI]:
    """Minimal placeholders when no curated catalog exists for the city."""
    slug = re.sub(r"[^a-z0-9]+", "-", (city or "destination").strip().lower()).strip("-") or "city"
    label = (city or "Destination").strip() or "Destination"
    # Neutral coords near Jaipur for Phase 1 demos; scheduler still needs lat/lon.
    return [
        POI(
            osm_id=f"well_known/{slug}-historic-center",
            name=f"{label} Historic Center",
            lat=26.9124,
            lon=75.7873,
            source="well_known",
            category="landmark",
        ),
        POI(
            osm_id=f"well_known/{slug}-main-market",
            name=f"{label} Main Market",
            lat=26.9180,
            lon=75.7950,
            source="well_known",
            category="shopping",
        ),
        POI(
            osm_id=f"well_known/{slug}-local-museum",
            name=f"{label} Museum",
            lat=26.9200,
            lon=75.8000,
            source="well_known",
            category="culture",
        ),
    ]


def parse_llm_pois_payload(content: str, *, city: str) -> list[dict[str, Any]]:
    """Best-effort parse of an LLM JSON list of POIs. Returns [] on failure."""
    if not content or "[stub response" in content:
        return []

    text = content.strip()
    # Allow fenced JSON blocks.
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw, list):
        return []

    slug = re.sub(r"[^a-z0-9]+", "-", city.strip().lower()).strip("-") or "city"
    pois: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        poi_id = str(item.get("osm_id") or item.get("poi_id") or f"llm/{slug}-{index}")
        pois.append(
            {
                "osm_id": poi_id,
                "name": name,
                "lat": lat,
                "lon": lon,
                "source": "llm",
                "category": item.get("category"),
                "tags": dict(item.get("tags") or {}),
            }
        )
    return pois
