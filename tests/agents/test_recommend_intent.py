"""Recommendation intent classification tests."""

from __future__ import annotations

from src.agents.supervisor.intent import classify_intent, is_recommend_message
from src.agents.supervisor.recommend import recommend_search_interests
from src.shared.messages.types import ConversationPhase, TaskType, TripConstraints


def test_suggest_food_places_is_recommend_not_confirm():
    constraints = TripConstraints(city="jaipur", days=3)
    intent = classify_intent(
        message="Suggest me some food places in Jaipur",
        constraints=constraints,
        phase=ConversationPhase.CONFIRM,
        has_sufficient=True,
        has_itinerary=False,
    )
    assert intent == TaskType.RECOMMEND


def test_recommend_cafes_with_itinerary():
    assert is_recommend_message("Recommend cafes in Jaipur")
    interests = recommend_search_interests("Recommend cafes")
    assert interests == ["food"]


def test_why_choose_city_palace_is_explain_not_recommend():
    constraints = TripConstraints(city="jaipur", days=2)
    intent = classify_intent(
        message="Why did you choose City Palace?",
        constraints=constraints,
        phase=ConversationPhase.ACTIVE,
        has_sufficient=True,
        has_itinerary=True,
    )
    assert intent == TaskType.EXPLAIN
    assert not is_recommend_message("Why did you choose City Palace?")


def test_confirm_flow_unchanged():
    constraints = TripConstraints(city="jaipur", days=3)
    intent = classify_intent(
        message="yes please",
        constraints=constraints,
        phase=ConversationPhase.CONFIRM,
        has_sufficient=True,
    )
    assert intent == TaskType.PLAN
