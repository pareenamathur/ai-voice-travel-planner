"""Tests for API — Supervisor-only entry point."""

from fastapi.testclient import TestClient
from src.api.deps import reset_registry
from src.api.main import app

client = TestClient(app)


def setup_function():
    reset_registry()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_session_message_routes_to_supervisor():
    response = client.post(
        "/api/session/message",
        json={"message": "Plan a trip to Jaipur"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "correlation_id" in data
    assert data["response"]
    # Supervisor clarifies missing days after extracting city — no specialist routes.
    assert "days" in data["response"].lower() or "understood" in data["response"].lower()
    assert data["itinerary_approved"] is False


def test_no_specialist_http_endpoints():
    """Specialist agents must not be exposed as HTTP routes."""
    for path in [
        "/api/planning",
        "/api/edit",
        "/api/knowledge",
        "/api/review",
        "/api/export",
    ]:
        response = client.post(path, json={})
        assert response.status_code == 404


def test_planning_failed_error_returns_friendly_200_not_500(monkeypatch):
    """Overpass/planning failures must surface as HTTP 200 with a clear message."""
    from src.agents.planning.errors import PlanningFailedError
    from src.api.deps import get_registry

    registry = get_registry()

    async def boom(session_id, message, correlation_id=None):  # type: ignore[no-untyped-def]
        raise PlanningFailedError(
            "I couldn't look up places for your trip right now because the map service "
            "is temporarily unavailable. Please try again in a moment.",
            session_id=session_id or "sess-fail",
            correlation_id="corr-fail",
        )

    monkeypatch.setattr(registry.supervisor, "handle_message", boom)

    response = client.post(
        "/api/session/message",
        json={"session_id": "sess-fail", "message": "yes"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess-fail"
    assert data["itinerary_approved"] is False
    assert data["intent"] == "plan"
    assert "unavailable" in data["response"].lower()
    assert data["task_message"] is None
