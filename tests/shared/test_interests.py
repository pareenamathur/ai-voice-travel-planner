"""Interest normalization and coverage helpers."""

from src.shared.interests import (
    extract_interests_from_text,
    missing_interests,
    normalize_interests,
    search_keys_for_interests,
)


def test_extract_food_and_adventure_from_jaipur_message():
    message = "Create a 3-day Jaipur itinerary including food and adventure."
    interests = extract_interests_from_text(message)
    assert "food" in interests
    assert "adventure" in interests


def test_normalize_interests_preserves_all_labels():
    assert normalize_interests(["Food", "ADVENTURE", "food"]) == ["food", "adventure"]


def test_search_keys_expand_adventure_and_nature():
    keys = search_keys_for_interests(["food", "adventure", "nature"])
    assert "food" in keys
    assert "adventure" in keys
    assert "nature" in keys


def test_missing_interests_detects_absent_category():
    pois = [
        {"osm_id": "1", "name": "Cafe", "category": "food"},
        {"osm_id": "2", "name": "Museum", "category": "culture"},
    ]
    assert missing_interests(["food", "adventure"], pois) == ["adventure"]
    assert missing_interests(["food", "culture"], pois) == []


def test_culture_and_shopping_combination():
    message = "Plan a trip with culture and shopping."
    interests = extract_interests_from_text(message)
    assert set(interests) == {"culture", "shopping"}


def test_food_nature_nightlife_combination():
    message = "I want food, nature, and nightlife on this trip."
    interests = extract_interests_from_text(message)
    assert set(interests) == {"food", "nature", "nightlife"}
