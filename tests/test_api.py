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
