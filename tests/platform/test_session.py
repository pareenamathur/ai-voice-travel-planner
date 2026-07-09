"""Tests for Session Manager."""

from src.platform.session.manager import SessionManager


def test_session_create_and_get():
    mgr = SessionManager()
    session = mgr.create()
    assert session.session_id
    assert mgr.get(session.session_id) is session


def test_session_get_or_create():
    mgr = SessionManager()
    s1 = mgr.get_or_create(None)
    s2 = mgr.get_or_create(s1.session_id)
    assert s1.session_id == s2.session_id


def test_session_update_fields():
    mgr = SessionManager()
    session = mgr.create()
    mgr.update_fields(session.session_id, itinerary_approved=True, clarifying_questions_asked=2)
    updated = mgr.get(session.session_id)
    assert updated.itinerary_approved is True
    assert updated.clarifying_questions_asked == 2
