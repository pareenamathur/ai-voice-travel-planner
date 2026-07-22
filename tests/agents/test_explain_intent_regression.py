"""Regression: trip-fit questions must classify as EXPLAIN when an itinerary exists."""

from __future__ import annotations

import pytest

from src.agents.supervisor.intent import classify_intent
from src.shared.messages.types import ConversationPhase, TaskType, TripConstraints

_DEFAULT_CONSTRAINTS = TripConstraints(city="Jaipur", days=4)

_ADVISORY_QUESTIONS = [
    "Is this plan doable?",
    "Is it kid-friendly?",
    "Is it senior citizen friendly?",
    "Is it wheelchair friendly?",
    "Is this too hectic?",
    "Is this safe?",
    "Is this expensive?",
    "What should I pack?",
    "Is this suitable during monsoon?",
    "Can I do this with elderly parents?",
]


@pytest.mark.parametrize("message", _ADVISORY_QUESTIONS)
def test_advisory_questions_classify_as_explain_with_itinerary(message: str):
    intent = classify_intent(
        message=message,
        constraints=_DEFAULT_CONSTRAINTS,
        phase=ConversationPhase.CONFIRM,
        has_sufficient=True,
        has_itinerary=True,
        itinerary_approved=True,
    )
    assert intent == TaskType.EXPLAIN, message


def test_advisory_explain_without_approval_still_explain():
    intent = classify_intent(
        message="Is this plan doable?",
        constraints=_DEFAULT_CONSTRAINTS,
        phase=ConversationPhase.ACTIVE,
        has_sufficient=True,
        has_itinerary=True,
        itinerary_approved=False,
    )
    assert intent == TaskType.EXPLAIN


def test_explicit_confirmation_still_plans_in_confirm_phase():
    intent = classify_intent(
        message="yes",
        constraints=_DEFAULT_CONSTRAINTS,
        phase=ConversationPhase.CONFIRM,
        has_sufficient=True,
        has_itinerary=False,
    )
    assert intent == TaskType.PLAN


def test_slot_refinement_without_itinerary_stays_confirm():
    intent = classify_intent(
        message="Make it 4 days with shopping",
        constraints=TripConstraints(city="jaipur", days=3),
        phase=ConversationPhase.CONFIRM,
        has_sufficient=True,
        has_itinerary=False,
    )
    assert intent == TaskType.CONFIRM
