"""Recommendation intent helpers — category → Gateway ``search_pois`` interests."""

from __future__ import annotations

import re

# Gateway POI Search accepts: food, culture, landmark, shopping (see INTEREST_MAP).
_RECOMMEND_TRIGGER_RE = re.compile(
    r"\b("
    r"suggest(?:ion|ions|ed|ing| me)?|recommend(?:ation|ations|ed|ing| me)?|"
    r"where should (?:i|we) (?:eat|shop|go)|where (?:can|could) (?:i|we) (?:eat|shop)|"
    r"where to (?:eat|shop|drink)|"
    r"best\s+(?:\w+\s+){0,2}(?:places?|spots?|cafes?|cafés?|restaurants?|bars?)|"
    r"good\s+(?:\w+\s+){0,2}(?:places?|spots?|breakfast|lunch|dinner)|"
    r"some\s+(?:\w+\s+){0,3}places?"
    r")\b",
    re.IGNORECASE,
)

_WHY_PLANNING_RE = re.compile(
    r"\bwhy\b.*\b(choose|chose|pick|picked|include|included|add|added|plan|planned)\b",
    re.IGNORECASE,
)

_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\b(street\s+food|food\s+places?|restaurants?|dining|eat|lunch|dinner|breakfast)\b", re.I), ["food"]),
    (re.compile(r"\b(cafes?|cafés?|coffee)\b", re.I), ["food"]),
    (re.compile(r"\b(nightlife|bars?|clubs?|pubs?)\b", re.I), ["food"]),
    (re.compile(r"\b(shopping|markets?|bazaar|souvenirs?)\b", re.I), ["shopping"]),
    (re.compile(r"\b(museums?|galleries?)\b", re.I), ["culture"]),
    (re.compile(r"\b(temples?|forts?|palaces?|monuments?)\b", re.I), ["landmark"]),
    (re.compile(r"\b(viewpoints?|sunset|sunrise\s+spots?)\b", re.I), ["landmark"]),
    (re.compile(r"\b(parks?|gardens?|nature)\b", re.I), ["landmark"]),
    (
        re.compile(r"\b(adventure|outdoor|outdoors|trekking|hiking|thrill)\b", re.I),
        ["landmark"],
    ),
    (re.compile(r"\b(local experiences?|hidden gems?|off\s+the\s+beaten)\b", re.I), ["landmark"]),
]


def is_recommend_message(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _WHY_PLANNING_RE.search(text):
        return False
    if _RECOMMEND_TRIGGER_RE.search(text):
        return True
    lower = text.lower()
    for pattern, _ in _CATEGORY_PATTERNS:
        if pattern.search(lower) and re.search(
            r"\b(places?|spots?|suggestions?|ideas?|options?)\b", lower
        ):
            return True
    return False


def recommend_search_interests(message: str) -> list[str]:
    """Map natural language to ``search_pois`` interest keys."""
    text = (message or "").lower()
    for pattern, interests in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return list(interests)
    if re.search(r"\b(suggest|recommend|where should|best|good)\b", text):
        return ["food"]
    return ["landmark"]


def recommend_category_label(message: str, interests: list[str]) -> str:
    text = (message or "").lower()
    for pattern, interests_for_pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            primary = interests_for_pattern[0]
            break
    else:
        primary = interests[0] if interests else "landmark"
    labels = {
        "food": "food and drink",
        "shopping": "shopping",
        "culture": "museums and culture",
        "landmark": "sightseeing and experiences",
    }
    return labels.get(primary, primary)
