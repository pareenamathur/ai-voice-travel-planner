"""Overpass QL query builder for POI Search (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterestQuery:
    category: str
    clauses: list[str]


INTEREST_MAP: dict[str, InterestQuery] = {
    # Food / drink
    "food": InterestQuery(
        category="food",
        clauses=[
            'nwr["amenity"="restaurant"](area.searchArea);',
            'nwr["amenity"="cafe"](area.searchArea);',
            'nwr["amenity"="fast_food"](area.searchArea);',
        ],
    ),
    # Culture
    "culture": InterestQuery(
        category="culture",
        clauses=[
            'nwr["tourism"="museum"](area.searchArea);',
            'nwr["tourism"="gallery"](area.searchArea);',
            'nwr["tourism"="artwork"](area.searchArea);',
            'nwr["amenity"="theatre"](area.searchArea);',
        ],
    ),
    # Landmarks / sights
    "landmark": InterestQuery(
        category="landmark",
        clauses=[
            'nwr["tourism"="attraction"](area.searchArea);',
            'nwr["historic"](area.searchArea);',
            'nwr["tourism"="viewpoint"](area.searchArea);',
        ],
    ),
    "sightseeing": InterestQuery(
        category="landmark",
        clauses=[
            'nwr["tourism"="attraction"](area.searchArea);',
            'nwr["historic"](area.searchArea);',
            'nwr["tourism"="viewpoint"](area.searchArea);',
        ],
    ),
    # Shopping / markets (useful for Jaipur)
    "shopping": InterestQuery(
        category="shopping",
        clauses=[
            'nwr["shop"](area.searchArea);',
            'nwr["amenity"="marketplace"](area.searchArea);',
        ],
    ),
    # Nature / parks / outdoors
    "nature": InterestQuery(
        category="nature",
        clauses=[
            'nwr["leisure"="park"](area.searchArea);',
            'nwr["leisure"="nature_reserve"](area.searchArea);',
            'nwr["natural"](area.searchArea);',
            'nwr["tourism"="viewpoint"](area.searchArea);',
        ],
    ),
    # Adventure / outdoor activities
    "adventure": InterestQuery(
        category="adventure",
        clauses=[
            'nwr["leisure"="sports_centre"](area.searchArea);',
            'nwr["sport"](area.searchArea);',
            'nwr["tourism"="theme_park"](area.searchArea);',
            'nwr["tourism"="zoo"](area.searchArea);',
            'nwr["tourism"="attraction"]["attraction"~"hiking|climbing|adventure|safari|zip|trek"](area.searchArea);',
            'nwr["leisure"="track"](area.searchArea);',
        ],
    ),
    # Nightlife
    "nightlife": InterestQuery(
        category="nightlife",
        clauses=[
            'nwr["amenity"="bar"](area.searchArea);',
            'nwr["amenity"="pub"](area.searchArea);',
            'nwr["amenity"="nightclub"](area.searchArea);',
        ],
    ),
    # Family-friendly attractions
    "family": InterestQuery(
        category="family",
        clauses=[
            'nwr["tourism"="zoo"](area.searchArea);',
            'nwr["tourism"="theme_park"](area.searchArea);',
            'nwr["tourism"="aquarium"](area.searchArea);',
            'nwr["leisure"="playground"](area.searchArea);',
            'nwr["tourism"="museum"](area.searchArea);',
        ],
    ),
}


def build_overpass_query(*, city: str, interests: list[str], timeout_s: int = 25) -> str:
    """Build Overpass QL for a city + interests.

    Notes:
    - We avoid the Overpass Turbo-only `{{geocodeArea:...}}` extension.
    - City scoping uses an `area` filter by name + administrative boundary. This is a best-effort
      heuristic for Phase 1 (Jaipur-focused); later phases can add better disambiguation.
    """

    from src.shared.interests import search_keys_for_interests

    search_keys = search_keys_for_interests(interests)
    clauses: list[str] = []
    seen_clauses: set[str] = set()
    for key in search_keys:
        mapped = INTEREST_MAP.get(key)
        if not mapped:
            continue
        for clause in mapped.clauses:
            if clause not in seen_clauses:
                seen_clauses.add(clause)
                clauses.append(clause)

    if not clauses:
        # Sensible default for empty/unknown interests.
        clauses = list(INTEREST_MAP["landmark"].clauses)

    city_escaped = city.replace('"', '\\"')

    return "\n".join(
        [
            f"[out:json][timeout:{timeout_s}];",
            f'area["name"="{city_escaped}"]["boundary"="administrative"]->.searchArea;',
            "(",
            *[f"  {c}" for c in clauses],
            ");",
            "out tags center;",
        ]
    )

