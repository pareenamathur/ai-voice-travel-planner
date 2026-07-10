"""Deterministic trip-constraint slot extraction (Phase 4 Task 2)."""

from __future__ import annotations

import re
from typing import Any

from src.shared.messages.types import TripConstraints

# Known demo cities (case-insensitive). Extend as corpus grows.
KNOWN_CITIES = (
    "jaipur",
    "delhi",
    "mumbai",
    "agra",
    "udaipur",
    "jaisalmer",
    "jodhpur",
    "varanasi",
    "goa",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "chennai",
    "kolkata",
    "pune",
)

INTEREST_KEYWORDS: dict[str, str] = {
    "food": "food",
    "cuisine": "food",
    "culinary": "food",
    "culture": "culture",
    "cultural": "culture",
    "heritage": "culture",
    "history": "culture",
    "museum": "culture",
    "shopping": "shopping",
    "nature": "nature",
    "park": "nature",
    "sightseeing": "sightseeing",
    "temple": "sightseeing",
    "fort": "sightseeing",
    "palace": "sightseeing",
}

PACE_KEYWORDS: dict[str, str] = {
    "relaxed": "relaxed",
    "relaxing": "relaxed",
    "leisurely": "relaxed",
    "slow": "relaxed",
    "moderate": "moderate",
    "balanced": "moderate",
    "fast": "fast",
    "packed": "packed",
    "busy": "packed",
    "intense": "packed",
}

BUDGET_KEYWORDS: dict[str, str] = {
    "low budget": "low",
    "on a budget": "low",
    "cheap": "low",
    "inexpensive": "low",
    "medium budget": "medium",
    "moderate budget": "medium",
    "mid-range": "medium",
    "midrange": "medium",
    "medium": "medium",
    "high budget": "high",
    "luxury": "high",
    "expensive": "high",
    "premium": "high",
}

FOOD_KEYWORDS: dict[str, str] = {
    "vegetarian": "vegetarian",
    "veg": "vegetarian",
    "vegan": "vegan",
    "non-veg": "non-vegetarian",
    "non vegetarian": "non-vegetarian",
    "halal": "halal",
    "jain": "jain",
}

TRANSPORT_KEYWORDS: dict[str, str] = {
    "walk": "walk",
    "walking": "walk",
    "metro": "metro",
    "train": "train",
    "taxi": "taxi",
    "cab": "taxi",
    "uber": "ride_hail",
    "ola": "ride_hail",
    "car": "car",
    "drive": "car",
    "bus": "bus",
}

REQUIRED_SLOTS = ("city", "days")

CLARIFICATION_QUESTIONS: dict[str, str] = {
    "city": "Which city would you like to visit?",
    "days": "How many days will you be traveling?",
    "interests": "What are you most interested in (for example food, culture, or sightseeing)?",
    "pace": "What pace do you prefer — relaxed, moderate, or packed?",
    "budget": "What is your budget level — low, medium, or high?",
}


def extract_slots(message: str) -> dict[str, Any]:
    """Extract available trip constraints from a user message.

    Returns a dict suitable for merging into ``TripConstraints``.
    Only keys with detected values are included.
    """
    text = message.strip()
    lower = text.lower()
    extracted: dict[str, Any] = {}

    city = _extract_city(lower)
    if city:
        extracted["city"] = city

    days = _extract_days(lower)
    if days is not None:
        extracted["days"] = days

    interests = _extract_keywords(lower, INTEREST_KEYWORDS)
    if interests:
        extracted["interests"] = interests

    pace = _extract_first_keyword(lower, PACE_KEYWORDS)
    if pace:
        extracted["pace"] = pace

    budget = _extract_first_keyword(lower, BUDGET_KEYWORDS)
    if budget:
        extracted["budget"] = budget

    travel_dates = _extract_travel_dates(text)
    if travel_dates:
        extracted["travel_dates"] = travel_dates

    food = _extract_keywords(lower, FOOD_KEYWORDS)
    if food:
        extracted["food_preferences"] = food

    transport = _extract_keywords(lower, TRANSPORT_KEYWORDS)
    if transport:
        extracted["transport_preferences"] = transport

    party_size = _extract_party_size(lower)
    if party_size is not None:
        extracted["party_size"] = party_size

    return extracted


def merge_constraints(
    existing: TripConstraints,
    extracted: dict[str, Any],
) -> TripConstraints:
    """Merge newly extracted slots onto existing session constraints."""
    if not extracted:
        return existing

    update = dict(extracted)
    for list_field in ("interests", "food_preferences", "transport_preferences"):
        if list_field in update:
            prior = list(getattr(existing, list_field) or [])
            merged: list[str] = []
            for item in prior + list(update[list_field]):
                if item not in merged:
                    merged.append(item)
            update[list_field] = merged

    return existing.model_copy(update=update)


def missing_required_slots(constraints: TripConstraints) -> list[str]:
    """Return required slot names that are still unset."""
    missing: list[str] = []
    if not constraints.city:
        missing.append("city")
    if constraints.days is None:
        missing.append("days")
    return missing


def next_clarification_slot(constraints: TripConstraints) -> str | None:
    """Pick the next slot to ask about (required first, then optional)."""
    for slot in REQUIRED_SLOTS:
        if slot == "city" and not constraints.city:
            return "city"
        if slot == "days" and constraints.days is None:
            return "days"

    if not constraints.interests:
        return "interests"
    if not constraints.pace:
        return "pace"
    if not constraints.budget:
        return "budget"
    return None


def has_sufficient_constraints(constraints: TripConstraints) -> bool:
    return not missing_required_slots(constraints)


def clarification_question(slot: str) -> str:
    return CLARIFICATION_QUESTIONS.get(
        slot,
        "Could you share a bit more about your trip preferences?",
    )


def format_confirmation_summary(constraints: TripConstraints) -> str:
    """Build the confirmation summary shown before PLAN."""
    lines = ["I understood the following:"]
    if constraints.city:
        lines.append(f"- City: {_title(constraints.city)}")
    if constraints.days is not None:
        lines.append(f"- Days: {constraints.days}")
    if constraints.budget:
        lines.append(f"- Budget: {_title(constraints.budget)}")
    if constraints.pace:
        lines.append(f"- Pace: {_title(constraints.pace)}")
    if constraints.interests:
        lines.append(f"- Interests: {', '.join(_title(i) for i in constraints.interests)}")
    if constraints.travel_dates:
        lines.append(f"- Travel dates: {constraints.travel_dates}")
    if constraints.party_size is not None:
        lines.append(f"- Companions / party size: {constraints.party_size}")
    if constraints.food_preferences:
        lines.append(
            f"- Food preferences: {', '.join(_title(f) for f in constraints.food_preferences)}"
        )
    if constraints.transport_preferences:
        lines.append(
            "- Transport preferences: "
            + ", ".join(_title(t) for t in constraints.transport_preferences)
        )
    lines.append("")
    lines.append("Would you like me to generate your itinerary?")
    return "\n".join(lines)


def constraints_payload(constraints: TripConstraints) -> dict[str, Any]:
    """JSON-serializable constraint payload for TaskMessage."""
    return constraints.model_dump(mode="json")


def _title(value: str) -> str:
    if value.lower() in {"low", "medium", "high"}:
        return value.capitalize()
    return value[:1].upper() + value[1:] if value else value


def _extract_city(lower: str) -> str | None:
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", lower):
            return city
    match = re.search(
        r"\b(?:to|in|visit(?:ing)?|for)\s+([a-z][a-z\s-]{1,30}?)(?:\s+(?:for|with|and|,|\.|!|\?|$))",
        lower,
    )
    if match:
        candidate = match.group(1).strip(" .,!?")
        if candidate and candidate not in {"a", "the", "my", "our", "trip", "vacation", "holiday"}:
            # Prefer known cities; otherwise accept single-token place names.
            if " " not in candidate and len(candidate) >= 3:
                return candidate
    return None


def _extract_days(lower: str) -> int | None:
    patterns = (
        r"\b(\d{1,2})\s*-\s*day\b",
        r"\b(\d{1,2})\s*days?\b",
        r"\bfor\s+(\d{1,2})\s*days?\b",
        r"\btotal[_\s]?days?\s*(?:is|=|:)?\s*(\d{1,2})\b",
        r"\b(\d{1,2})\s*nights?\b",
    )
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            days = int(match.group(1))
            if 1 <= days <= 30:
                return days
    return None


def _extract_party_size(lower: str) -> int | None:
    patterns = (
        r"\b(?:party(?:\s*size)?|companions?|travelers?|travellers?|people|adults)\s*(?:of|is|=|:)?\s*(\d{1,2})\b",
        r"\b(\d{1,2})\s*(?:people|adults|travelers|travellers|companions)\b",
        r"\b(?:with\s+)?(?:my\s+)?(?:partner|spouse|wife|husband)\b",
        r"\bfamily\s+of\s+(\d{1,2})\b",
        r"\bsolo\b",
        r"\bcouple\b",
    )
    if re.search(r"\bsolo\b", lower):
        return 1
    if re.search(r"\bcouple\b", lower) or re.search(
        r"\b(?:with\s+)?(?:my\s+)?(?:partner|spouse|wife|husband)\b", lower
    ):
        return 2
    for pattern in patterns[:2] + (patterns[3],):
        match = re.search(pattern, lower)
        if match:
            size = int(match.group(1))
            if 1 <= size <= 20:
                return size
    return None


def _extract_travel_dates(text: str) -> str | None:
    lower = text.lower()
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        second = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text[iso.end() :])
        if second:
            return f"{iso.group(1)} to {second.group(1)}"
        return iso.group(1)

    range_match = re.search(
        r"\b(?:from\s+)?([A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)"
        r"\s*(?:to|-|through)\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if range_match:
        return f"{range_match.group(1)} to {range_match.group(2)}"

    month_match = re.search(
        r"\b(?:in|during)\s+((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
        r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?)\b",
        lower,
    )
    if month_match:
        return month_match.group(1).strip()
    return None


def _extract_keywords(lower: str, mapping: dict[str, str]) -> list[str]:
    found: list[str] = []
    # Longer phrases first to prefer "non vegetarian" over "vegetarian".
    for phrase, label in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lower) and label not in found:
            found.append(label)
    return found


def _extract_first_keyword(lower: str, mapping: dict[str, str]) -> str | None:
    for phrase, label in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            return label
    return None
