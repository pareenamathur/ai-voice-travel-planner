"""Tests for Session Manager (Phase 4 Task 1)."""

from __future__ import annotations

import pytest
from src.platform.session import (
    MAX_CLARIFYING_QUESTIONS,
    ClarificationLimitReachedError,
    SessionManager,
    SessionNotFoundError,
)
from src.shared.itinerary import Itinerary
from src.shared.messages.types import ConversationPhase, ReviewStatus, TripConstraints

SAMPLE_ITINERARY = {
    "city": "Jaipur",
    "total_days": 2,
    "traveler_constraints": {"pace": "relaxed"},
    "days": [
        {"day_number": 1, "activities": [], "travel_segments": []},
        {"day_number": 2, "activities": [], "travel_segments": []},
    ],
    "poi_registry": [],
    "citations": [],
    "metadata": {},
}


def test_session_create_and_get():
    mgr = SessionManager()
    session = mgr.create()

    assert session.session_id
    assert session.trip_constraints == TripConstraints()
    assert session.clarifying_questions_asked == 0
    assert session.itinerary is None
    assert session.itinerary_approved is False
    assert session.last_eval_report is None
    assert session.conversation_history == []
    assert session.metadata == {}
    assert session.conversation_phase == ConversationPhase.INTAKE
    assert mgr.get(session.session_id) is session


def test_session_schema_aliases():
    session = SessionManager().create()
    session.trip_constraints = TripConstraints(city="Jaipur", days=3)

    assert session.user_constraints.city == "Jaipur"
    assert session.clarification_count == 0


def test_session_get_or_create():
    mgr = SessionManager()
    created = mgr.get_or_create(None)
    loaded = mgr.get_or_create(created.session_id)

    assert created.session_id == loaded.session_id


def test_session_update_fields_backward_compatible():
    mgr = SessionManager()
    session = mgr.create()
    mgr.update_fields(session.session_id, itinerary_approved=True, clarifying_questions_asked=2)

    updated = mgr.get(session.session_id)
    assert updated is not None
    assert updated.itinerary_approved is True
    assert updated.clarifying_questions_asked == 2


def test_read_requires_existing_session():
    mgr = SessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.read("missing-session")


def test_update_constraints_merges_user_constraints():
    mgr = SessionManager()
    session = mgr.create()
    mgr.update_constraints(session.session_id, {"city": "Jaipur", "days": 3})
    mgr.update_constraints(session.session_id, {"interests": ["food", "culture"]})

    updated = mgr.read(session.session_id)
    assert updated.trip_constraints.city == "Jaipur"
    assert updated.trip_constraints.days == 3
    assert updated.trip_constraints.interests == ["food", "culture"]


def test_append_conversation_history():
    mgr = SessionManager()
    session = mgr.create()

    mgr.append_conversation_turn(
        session.session_id,
        role="user",
        content="Plan a trip to Jaipur",
        correlation_id="turn-1",
    )
    mgr.append_conversation_turn(
        session.session_id,
        role="assistant",
        content="How many days?",
        correlation_id="turn-1",
    )

    updated = mgr.read(session.session_id)
    assert len(updated.conversation_history) == 2
    assert updated.conversation_history[0].role == "user"
    assert updated.conversation_history[1].content == "How many days?"
    assert updated.conversation_history[0].correlation_id == "turn-1"


def test_clarification_count_increment_and_cap():
    mgr = SessionManager()
    session = mgr.create()

    assert mgr.can_ask_clarification(session.session_id) is True

    for _ in range(MAX_CLARIFYING_QUESTIONS):
        mgr.increment_clarification_count(session.session_id)

    updated = mgr.read(session.session_id)
    assert updated.clarifying_questions_asked == MAX_CLARIFYING_QUESTIONS
    assert updated.clarification_count == MAX_CLARIFYING_QUESTIONS
    assert mgr.can_ask_clarification(session.session_id) is False

    with pytest.raises(ClarificationLimitReachedError):
        mgr.increment_clarification_count(session.session_id)


def test_set_itinerary_and_validate_against_shared_schema():
    mgr = SessionManager()
    session = mgr.create()

    Itinerary.model_validate(SAMPLE_ITINERARY)
    mgr.set_itinerary(
        session.session_id,
        SAMPLE_ITINERARY,
        poi_registry={"node/1": {"name": "City Palace"}},
        rag_citations=[{"citation_id": "jaipur:wikivoyage#see#0001"}],
    )

    updated = mgr.read(session.session_id)
    assert updated.itinerary == SAMPLE_ITINERARY
    assert updated.poi_registry["node/1"]["name"] == "City Palace"
    assert updated.rag_citations[0]["citation_id"] == "jaipur:wikivoyage#see#0001"


def test_set_itinerary_approved_and_eval_report():
    mgr = SessionManager()
    session = mgr.create()
    report = {
        "entries": [
            {"name": "feasibility", "passed": True, "reasons": []},
            {"name": "grounding", "passed": True, "reasons": []},
        ]
    }

    mgr.record_eval_report(
        session.session_id,
        report,
        verdict=ReviewStatus.PASS,
    )
    mgr.set_itinerary_approved(session.session_id, True)

    updated = mgr.read(session.session_id)
    assert updated.last_eval_report == report
    assert updated.last_review_verdict == ReviewStatus.PASS.value
    assert updated.itinerary_approved is True


def test_update_metadata_and_conversation_phase():
    mgr = SessionManager()
    session = mgr.create()

    mgr.update_metadata(session.session_id, source="text", locale="en-IN")
    mgr.set_conversation_phase(session.session_id, ConversationPhase.CONFIRM)

    updated = mgr.read(session.session_id)
    assert updated.metadata["source"] == "text"
    assert updated.metadata["locale"] == "en-IN"
    assert updated.conversation_phase == ConversationPhase.CONFIRM


def test_session_delete_and_list():
    mgr = SessionManager()
    session = mgr.create()
    session_id = session.session_id

    assert session_id in mgr.list_session_ids()
    assert mgr.delete(session_id) is True
    assert mgr.get(session_id) is None
    assert mgr.delete(session_id) is False


def test_session_model_json_round_trip():
    mgr = SessionManager()
    session = mgr.create()
    mgr.update_constraints(session.session_id, {"city": "Jaipur"})
    mgr.append_conversation_turn(session.session_id, role="user", content="Hello")

    payload = mgr.read(session.session_id).model_dump(mode="json")
    reloaded = mgr.update_fields(session.session_id, metadata=payload["metadata"])

    assert reloaded.session_id == session.session_id
    assert reloaded.trip_constraints.city == "Jaipur"
    assert len(reloaded.conversation_history) == 1
