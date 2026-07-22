"""Edit intent parsing for scoped itinerary modifications (Phase 6)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_DAY_NUMBER_RE = re.compile(
    r"\b(?:day\s*(\d+)|(\d)(?:st|nd|rd|th)\s+day|first\s+day|second\s+day|third\s+day|fourth\s+day)\b",
    re.IGNORECASE,
)
_RELAX_RE = re.compile(r"\b(relax(?:ed|ing)?|more\s+relax(?:ed|ing)?|slower\s+pace)\b", re.IGNORECASE)
_LUXURY_RE = re.compile(r"\b(luxur(?:y|ious)|more\s+upscale|premium|high\s+end)\b", re.IGNORECASE)
_ADVENTURE_PACE_RE = re.compile(
    r"\b(adventur(?:e|ous)|more\s+outdoor|outdoors|spend more time outdoors)\b",
    re.IGNORECASE,
)
_FOOD_TOUR_RE = re.compile(
    r"\b(make|turn)\b.*\b(day\s*\d+|\d(?:st|nd|rd|th)\s+day|first|second|third|fourth)\b.*\bfood\s+tour\b"
    r"|\bfood\s+tour\b.*\b(day\s*\d+|\d(?:st|nd|rd|th)\s+day|first|second|third|fourth)\b",
    re.IGNORECASE,
)
_REPLACE_DAY_CITY_RE = re.compile(
    r"\breplace\b.*\b(day\s*(?P<day>\d+)|(?P<ord>first|second|third|fourth)\s+day)\b"
    r".*\bwith\b\s+(?P<city>[A-Za-z][\w\s-]{2,30})",
    re.IGNORECASE,
)
_REPLACE_CATEGORY_RE = re.compile(
    r"\breplace\s+(?P<from>museums?|culture|shopping|food|cafes?|cafés?|adventure|landmarks?)"
    r"\s+with\s+(?P<to>museums?|culture|shopping|food|cafes?|cafés?|adventure|landmarks?)\b",
    re.IGNORECASE,
)
_ADD_CAFE_RE = re.compile(r"\b(add|include)\b.*\b(cafe|café|coffee)\b", re.IGNORECASE)
_ADD_FOOD_RE = re.compile(
    r"\b(add|include)\b.*\b("
    r"food|restaurant|meal|lunch|dinner|breakfast|"
    r"famous\s+local\s+food|local\s+food|food\s+place"
    r")\b",
    re.IGNORECASE,
)
_ADD_ADVENTURE_RE = re.compile(r"\b(add|include)\b.*\b(adventure|thrill|outdoor)\b", re.IGNORECASE)
_REMOVE_RE = re.compile(
    r"\b(remove|delete|drop|skip)\b.*?(?P<name>[A-Za-z][\w\s'-]{2,40})",
    re.IGNORECASE,
)
_REPLACE_NAMED_RE = re.compile(
    r"\b(replace|swap\s+out)\b\s+(?:the\s+)?(?P<name>[A-Za-z][\w\s'-]{2,40}?)"
    r"(?:\s+with\s+(?P<with>[A-Za-z][\w\s'-]{2,40}))?\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(
    r"\bmove\b\s+(?:the\s+)?(?P<name>[A-Za-z][\w\s'-]{2,40}?)\s+to\s+"
    r"(?:day\s*(?P<day>\d+)|(?P<ord>first|second|third|fourth)\s+day)\b",
    re.IGNORECASE,
)
_REDUCE_TRAVEL_RE = re.compile(
    r"\b(reduce|minimi[sz]e|cut|less|lower)\b.*\btravel(\s+time)?\b"
    r"|\b(optimize|optimise|shorter)\b.*\b(route|travel|commute)\b",
    re.IGNORECASE,
)
_INDOORS_RE = re.compile(
    r"\b(indoors?|indoor|something indoors|rainy[- ]day)\b",
    re.IGNORECASE,
)
_CHANGE_LUNCH_RE = re.compile(
    r"\b(change|swap|replace)\b.*\b(lunch|lunch\s+recommendation)\b",
    re.IGNORECASE,
)
_QUOTED_NAME_RE = re.compile(r"[\"']([^\"']+)[\"']")

_CATEGORY_ALIASES: dict[str, str] = {
    "museum": "culture",
    "museums": "culture",
    "culture": "culture",
    "shopping": "shopping",
    "food": "food",
    "cafe": "food",
    "cafes": "food",
    "café": "food",
    "cafés": "food",
    "coffee": "food",
    "adventure": "landmark",
    "thrill": "landmark",
    "outdoor": "landmark",
    "landmark": "landmark",
    "landmarks": "landmark",
}

_ORD_MAP = {"first": 1, "second": 2, "third": 3, "fourth": 4}


@dataclass(frozen=True, slots=True)
class ParsedEditIntent:
    action: str
    day_number: int | None = None
    target_category: str | None = None
    replacement_category: str | None = None
    target_name: str | None = None
    replacement_name: str | None = None
    raw_intent: str = ""


def parse_edit_intent(message: str, *, default_day: int | None = None) -> ParsedEditIntent | None:
    """Best-effort parse of conversational edit requests."""
    text = (message or "").strip()
    if not text:
        return None

    day_number = _extract_day_number(text) or default_day

    replace_city = _REPLACE_DAY_CITY_RE.search(text)
    if replace_city:
        city_raw = replace_city.group("city").strip()
        city_raw = re.sub(r"\b(please|thanks|itinerary)\b.*$", "", city_raw, flags=re.I).strip()
        day_from_match = replace_city.group("day")
        if day_from_match:
            day_number = int(day_from_match)
        else:
            ord_label = (replace_city.group("ord") or "").lower()
            day_number = _ORD_MAP.get(ord_label, day_number)
        return ParsedEditIntent(
            action="replace_day_city",
            day_number=day_number,
            target_name=city_raw,
            raw_intent=text,
        )

    move_match = _MOVE_RE.search(text)
    if move_match:
        dest = move_match.group("day")
        if dest:
            day_number = int(dest)
        else:
            day_number = _ORD_MAP.get((move_match.group("ord") or "").lower(), day_number)
        return ParsedEditIntent(
            action="move_location",
            day_number=day_number,
            target_name=_clean_target_name(move_match.group("name").strip()),
            raw_intent=text,
        )

    if _FOOD_TOUR_RE.search(text):
        day_number = _extract_day_number(text) or day_number
        return ParsedEditIntent(
            action="food_tour",
            day_number=day_number,
            raw_intent=text,
        )

    replace_match = _REPLACE_CATEGORY_RE.search(text)
    if replace_match:
        return ParsedEditIntent(
            action="replace_category",
            day_number=day_number,
            target_category=_normalize_category(replace_match.group("from")),
            replacement_category=_normalize_category(replace_match.group("to")),
            raw_intent=text,
        )

    if _CHANGE_LUNCH_RE.search(text):
        return ParsedEditIntent(
            action="change_lunch",
            day_number=day_number,
            raw_intent=text,
        )

    if _ADD_CAFE_RE.search(text):
        return ParsedEditIntent(
            action="add_cafe",
            day_number=day_number,
            raw_intent=text,
        )

    if _ADD_FOOD_RE.search(text):
        return ParsedEditIntent(
            action="add_food",
            day_number=day_number,
            raw_intent=text,
        )

    if _ADD_ADVENTURE_RE.search(text):
        return ParsedEditIntent(
            action="add_adventure",
            day_number=day_number,
            raw_intent=text,
        )

    if _INDOORS_RE.search(text) and re.search(
        r"\b(swap|change|make|replace|evening|plan)\b", text, re.I
    ):
        return ParsedEditIntent(
            action="make_indoors",
            day_number=day_number,
            raw_intent=text,
        )

    if _REDUCE_TRAVEL_RE.search(text):
        return ParsedEditIntent(
            action="reduce_travel",
            day_number=day_number,
            raw_intent=text,
        )

    remove_match = _REMOVE_RE.search(text)
    if remove_match:
        name = remove_match.group("name").strip()
        quoted = _QUOTED_NAME_RE.search(text)
        if quoted:
            name = quoted.group(1).strip()
        return ParsedEditIntent(
            action="remove_location",
            day_number=day_number,
            target_name=_clean_target_name(name),
            raw_intent=text,
        )

    replace_named = _REPLACE_NAMED_RE.search(text)
    if replace_named and not _REPLACE_CATEGORY_RE.search(text):
        name = replace_named.group("name").strip()
        with_name = replace_named.group("with")
        return ParsedEditIntent(
            action="replace_location",
            day_number=day_number,
            target_name=_clean_target_name(name),
            replacement_name=_clean_target_name(with_name.strip()) if with_name else None,
            raw_intent=text,
        )

    if _RELAX_RE.search(text):
        return ParsedEditIntent(
            action="relax_day",
            day_number=day_number,
            raw_intent=text,
        )

    if _LUXURY_RE.search(text):
        return ParsedEditIntent(
            action="luxury_pace",
            day_number=day_number,
            raw_intent=text,
        )

    if _ADVENTURE_PACE_RE.search(text):
        return ParsedEditIntent(
            action="outdoors_day",
            day_number=day_number,
            raw_intent=text,
        )

    # Generic edit verbs when an itinerary already exists.
    if re.search(
        r"\b(make|adjust|update|modify|change|swap|replace|add|remove|move|reduce)\b",
        text,
        re.I,
    ):
        return ParsedEditIntent(
            action="generic",
            day_number=day_number,
            raw_intent=text,
        )

    return None


def is_edit_message(message: str) -> bool:
    return parse_edit_intent(message) is not None


def _extract_day_number(text: str) -> int | None:
    match = _DAY_NUMBER_RE.search(text)
    if not match:
        return None
    if match.group(1):
        return int(match.group(1))
    if match.group(2):
        return int(match.group(2))
    lowered = text.lower()
    for index, label in enumerate(("first", "second", "third", "fourth"), start=1):
        if f"{label} day" in lowered:
            return index
    return None


def _normalize_category(value: str | None) -> str | None:
    if not value:
        return None
    return _CATEGORY_ALIASES.get(value.strip().lower(), value.strip().lower())


def _clean_target_name(name: str) -> str:
    cleaned = re.sub(
        r"\b(from|on|for|please|thanks|thank you|day \d+|with .+)\b.*$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip(" .,!")
    return cleaned or name.strip()
