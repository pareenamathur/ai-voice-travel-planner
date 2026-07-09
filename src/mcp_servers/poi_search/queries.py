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
    # Shopping / markets (useful for Jaipur)
    "shopping": InterestQuery(
        category="shopping",
        clauses=[
            'nwr["shop"](area.searchArea);',
            'nwr["amenity"="marketplace"](area.searchArea);',
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

    interests_norm = [i.strip().lower() for i in interests if i.strip()]
    clauses: list[str] = []
    for interest in interests_norm:
        mapped = INTEREST_MAP.get(interest)
        if mapped:
            clauses.extend(mapped.clauses)

    if not clauses:
        # Sensible default for empty/unknown interests.
        clauses = INTEREST_MAP["landmark"].clauses

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

