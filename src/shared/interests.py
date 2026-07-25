"""Canonical interest normalization for slot extraction, POI search, and review."""

from __future__ import annotations

import re
from typing import Iterable

# User-facing keywords → canonical interest label stored on TripConstraints.
INTEREST_KEYWORDS: dict[str, str] = {
    "food": "food",
    "cuisine": "food",
    "culinary": "food",
    "dining": "food",
    "restaurant": "food",
    "culture": "culture",
    "cultural": "culture",
    "heritage": "culture",
    "history": "culture",
    "historical": "culture",
    "museum": "culture",
    "shopping": "shopping",
    "market": "shopping",
    "markets": "shopping",
    "nature": "nature",
    "park": "nature",
    "parks": "nature",
    "wildlife": "nature",
    "sightseeing": "sightseeing",
    "temple": "sightseeing",
    "fort": "sightseeing",
    "palace": "sightseeing",
    "landmark": "sightseeing",
    "landmarks": "sightseeing",
    "adventure": "adventure",
    "adventurous": "adventure",
    "outdoor": "adventure",
    "outdoors": "adventure",
    "hiking": "adventure",
    "trekking": "adventure",
    "sports": "adventure",
    "thrill": "adventure",
    "nightlife": "nightlife",
    "night life": "nightlife",
    "bars": "nightlife",
    "clubs": "nightlife",
    "family": "family",
    "families": "family",
    "kids": "family",
    "children": "family",
    "family activities": "family",
    "family-friendly": "family",
}

# Canonical interest → POI categories that satisfy traveler coverage checks.
INTEREST_POI_CATEGORIES: dict[str, frozenset[str]] = {
    "food": frozenset({"food"}),
    "culture": frozenset({"culture"}),
    "shopping": frozenset({"shopping"}),
    "nature": frozenset({"nature", "park", "viewpoint"}),
    "sightseeing": frozenset({"landmark", "sightseeing", "culture"}),
    "adventure": frozenset({"adventure", "nature", "sports", "landmark"}),
    "nightlife": frozenset({"nightlife", "food"}),
    "family": frozenset({"family", "landmark", "culture", "nature", "adventure"}),
}

# Canonical interest → Overpass INTEREST_MAP keys used for live lookup.
INTEREST_SEARCH_KEYS: dict[str, tuple[str, ...]] = {
    "food": ("food",),
    "culture": ("culture",),
    "shopping": ("shopping",),
    "nature": ("nature",),
    "sightseeing": ("sightseeing",),
    "adventure": ("adventure",),
    "nightlife": ("nightlife",),
    "family": ("family",),
}


def extract_interests_from_text(text: str) -> list[str]:
    """Extract canonical interests from free-form user text."""
    lower = (text or "").strip().lower()
    if not lower:
        return []
    found: list[str] = []
    for phrase, label in sorted(INTEREST_KEYWORDS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lower) and label not in found:
            found.append(label)
    return found


def normalize_interests(interests: Iterable[str] | None) -> list[str]:
    """Normalize and dedupe interest labels while preserving order."""
    normalized: list[str] = []
    for raw in interests or []:
        token = (raw or "").strip().lower()
        if not token:
            continue
        canonical = INTEREST_KEYWORDS.get(token, token)
        if canonical not in normalized:
            normalized.append(canonical)
    return normalized


def search_keys_for_interests(interests: Iterable[str] | None) -> list[str]:
    """Expand canonical interests into Overpass search keys (deduped, ordered)."""
    keys: list[str] = []
    for interest in normalize_interests(interests):
        for key in INTEREST_SEARCH_KEYS.get(interest, (interest,)):
            if key not in keys:
                keys.append(key)
    return keys


def poi_categories_for_interest(interest: str) -> frozenset[str]:
    """POI categories that satisfy a requested interest."""
    canonical = INTEREST_KEYWORDS.get(interest.strip().lower(), interest.strip().lower())
    return INTEREST_POI_CATEGORIES.get(canonical, frozenset({canonical}))


def poi_satisfies_interest(poi: dict[str, object], interest: str) -> bool:
    """Return True when a POI category matches the requested interest."""
    category = str(poi.get("category") or "").strip().lower()
    if not category:
        return False
    return category in poi_categories_for_interest(interest)


def covered_interests(
    interests: Iterable[str] | None,
    pois: Iterable[dict[str, object]],
) -> set[str]:
    """Return the subset of requested interests represented in POI results."""
    requested = normalize_interests(interests)
    poi_list = list(pois)
    covered: set[str] = set()
    for interest in requested:
        if any(poi_satisfies_interest(poi, interest) for poi in poi_list):
            covered.add(interest)
    return covered


def missing_interests(
    interests: Iterable[str] | None,
    pois: Iterable[dict[str, object]],
) -> list[str]:
    """Return requested interests with no matching POI category in the pool."""
    requested = normalize_interests(interests)
    present = covered_interests(requested, pois)
    return [interest for interest in requested if interest not in present]
