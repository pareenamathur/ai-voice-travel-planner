"""Well-known / curated fallback POIs when live Overpass lookup is unavailable."""

from __future__ import annotations

import json
import re
from typing import Any

from src.mcp_servers.poi_search.models import POI
from src.shared.interests import (
    missing_interests,
    normalize_interests,
    poi_satisfies_interest,
)

CURATED_SOURCE = "well_known"
LIVE_SOURCES = frozenset({"osm", "city_cache"})

LIVE_POI_UNAVAILABLE_NOTE = (
    "Live place lookup was temporarily unavailable. This itinerary uses curated "
    "destination guidance instead of live map data."
)

UNVERIFIED_INTERESTS_NOTE = (
    "We could not verify suitable places for: {interests}. "
    "Those interests are not included as verified stops."
)

# LLM payloads must never contribute schedulable POIs or unverified place metadata.
_FORBIDDEN_LLM_TAG_KEYS = frozenset(
    {
        "opening_hours",
        "opening_hours:start",
        "opening_hours:end",
        "addr:full",
        "addr:street",
        "addr:housenumber",
        "address",
        "rating",
        "stars",
        "website",
        "phone",
        "url",
        "contact:website",
        "contact:phone",
    }
)

# Stable synthetic ids so itinerary builder / registry stay consistent across runs.
WELL_KNOWN_BY_CITY: dict[str, list[POI]] = {
    "jaipur": [
        POI(
            osm_id="well_known/jaipur-city-palace",
            name="City Palace",
            lat=26.9258,
            lon=75.8236,
            source=CURATED_SOURCE,
            category="culture",
        ),
        POI(
            osm_id="well_known/jaipur-hawa-mahal",
            name="Hawa Mahal",
            lat=26.9239,
            lon=75.8267,
            source=CURATED_SOURCE,
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-amber-fort",
            name="Amber Fort",
            lat=26.9855,
            lon=75.8513,
            source=CURATED_SOURCE,
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-jantar-mantar",
            name="Jantar Mantar",
            lat=26.9247,
            lon=75.8246,
            source=CURATED_SOURCE,
            category="culture",
        ),
        POI(
            osm_id="well_known/jaipur-jal-mahal",
            name="Jal Mahal",
            lat=26.9535,
            lon=75.8463,
            source=CURATED_SOURCE,
            category="landmark",
        ),
        POI(
            osm_id="well_known/jaipur-bapu-bazaar",
            name="Bapu Bazaar",
            lat=26.9170,
            lon=75.8205,
            source=CURATED_SOURCE,
            category="shopping",
        ),
        POI(
            osm_id="well_known/jaipur-lmb",
            name="Laxmi Misthan Bhandar (LMB)",
            lat=26.9190,
            lon=75.8265,
            source=CURATED_SOURCE,
            category="food",
        ),
        POI(
            osm_id="well_known/jaipur-indian-coffee-house",
            name="Indian Coffee House",
            lat=26.9152,
            lon=75.8189,
            source=CURATED_SOURCE,
            category="food",
        ),
        POI(
            osm_id="well_known/jaipur-peacock-rooftop",
            name="Peacock Rooftop Restaurant",
            lat=26.9245,
            lon=75.8260,
            source=CURATED_SOURCE,
            category="food",
        ),
        POI(
            osm_id="well_known/jaipur-rawat-misthan",
            name="Rawat Misthan Bhandar",
            lat=26.9128,
            lon=75.7878,
            source=CURATED_SOURCE,
            category="food",
        ),
        POI(
            osm_id="well_known/jaipur-chokhi-dhani",
            name="Chokhi Dhani",
            lat=26.7665,
            lon=75.8360,
            source=CURATED_SOURCE,
            category="food",
        ),
        POI(
            osm_id="well_known/jaipur-jhalana-safari",
            name="Jhalana Leopard Safari Park",
            lat=26.8712,
            lon=75.8294,
            source=CURATED_SOURCE,
            category="adventure",
        ),
        POI(
            osm_id="well_known/jaipur-nahargarh-fort",
            name="Nahargarh Fort",
            lat=26.9388,
            lon=75.8155,
            source=CURATED_SOURCE,
            category="adventure",
        ),
    ],
}


# Dining / nightlife — available for Knowledge recommendations, not default sightseeing.
_DINING_CATEGORIES = frozenset({"food"})


def has_curated_catalog(city: str) -> bool:
    key = (city or "").strip().lower()
    return bool(WELL_KNOWN_BY_CITY.get(key))


def is_live_poi(poi: dict[str, Any]) -> bool:
    return str(poi.get("source") or "").strip().lower() in LIVE_SOURCES


def is_curated_poi(poi: dict[str, Any]) -> bool:
    return str(poi.get("source") or "").strip().lower() == CURATED_SOURCE


def curated_pois_for_city(city: str, *, interests: list[str] | None = None) -> list[dict[str, Any]]:
    """Return only explicit curated-catalog POIs for a city (never generic placeholders)."""
    key = (city or "").strip().lower()
    pois = list(WELL_KNOWN_BY_CITY.get(key) or [])
    return _filter_curated_pois(pois, interests)


def well_known_pois_for_city(city: str, *, interests: list[str] | None = None) -> list[dict[str, Any]]:
    """Return curated attractions for a city, optionally filtered by interest category."""
    return curated_pois_for_city(city, interests=interests)


def missing_curated_interests(city: str, interests: list[str] | None) -> list[str]:
    """Interests with no matching curated POI for the city."""
    catalog = curated_pois_for_city(city, interests=interests)
    return missing_interests(interests, catalog)


def curated_for_missing_interests(
    city: str,
    *,
    interests: list[str] | None,
    existing_pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return curated POIs only for requested interests not already represented."""
    gaps = missing_interests(interests, existing_pois)
    if not gaps:
        return []
    catalog = curated_pois_for_city(city, interests=gaps)
    return [
        poi
        for poi in catalog
        if any(poi_satisfies_interest(poi, interest) for interest in gaps)
    ]


def merge_live_and_curated_pois(
    live_pois: list[dict[str, Any]],
    curated_pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve verified live POIs and add non-duplicative curated entries."""
    merged = list(live_pois)
    seen_ids = {str(p.get("osm_id") or p.get("poi_id") or "") for p in merged}
    seen_names = {str(p.get("name") or "").strip().lower() for p in merged}
    for poi in curated_pois:
        poi_id = str(poi.get("osm_id") or poi.get("poi_id") or "")
        name = str(poi.get("name") or "").strip().lower()
        if poi_id and poi_id in seen_ids:
            continue
        if name and name in seen_names:
            continue
        merged.append(poi)
        if poi_id:
            seen_ids.add(poi_id)
        if name:
            seen_names.add(name)
    return merged


def parse_llm_pois_payload(content: str, *, city: str) -> list[dict[str, Any]]:
    """Reject LLM POI payloads for scheduling — they may invent places or coordinates."""
    _ = city
    if not content or "[stub response" in content:
        return []

    text = content.strip()
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

    # Safety policy: never schedule LLM-generated places or coordinates.
    return []


def _filter_curated_pois(pois: list[POI], interests: list[str] | None) -> list[dict[str, Any]]:
    interests_norm = normalize_interests(interests)
    if "food" not in interests_norm:
        pois = [
            p for p in pois if (p.category or "").lower() not in _DINING_CATEGORIES
        ]
    if interests_norm:
        matched = [
            p
            for p in pois
            if any(
                poi_satisfies_interest(p.model_dump(), interest) for interest in interests_norm
            )
        ]
        if matched:
            pois = matched + [p for p in pois if p not in matched]
    return [_sanitize_curated_poi(p.model_dump()) for p in pois]


def _sanitize_curated_poi(poi: dict[str, Any]) -> dict[str, Any]:
    tags = {
        key: value
        for key, value in dict(poi.get("tags") or {}).items()
        if key not in _FORBIDDEN_LLM_TAG_KEYS
    }
    return {
        "osm_id": poi.get("osm_id"),
        "name": poi.get("name"),
        "lat": poi.get("lat"),
        "lon": poi.get("lon"),
        "source": CURATED_SOURCE,
        "category": poi.get("category"),
        "tags": tags,
        "verified_live": False,
        "catalog": "curated",
    }
