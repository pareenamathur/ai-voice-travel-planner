"""Internal export render route (n8n HTTP workflow)."""

import base64

import pytest
from fastapi.testclient import TestClient

from src.api.config import settings
from src.api.main import app

client = TestClient(app)


@pytest.fixture
def render_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = "test-render-secret"
    monkeypatch.setattr(settings, "export_render_secret", secret)
    return secret


def test_internal_render_disabled_without_secret() -> None:
    original = settings.export_render_secret
    settings.export_render_secret = ""
    try:
        response = client.post(
            "/api/internal/export/render",
            json={"itinerary": {"days": []}, "export_format": "json"},
            headers={"X-Export-Render-Key": "any"},
        )
        assert response.status_code == 404
    finally:
        settings.export_render_secret = original


def test_internal_render_rejects_bad_key(render_secret: str) -> None:
    response = client.post(
        "/api/internal/export/render",
        json={"itinerary": {"days": [], "poi_registry": []}, "export_format": "markdown"},
        headers={"X-Export-Render-Key": "wrong"},
    )
    assert response.status_code == 403


def test_internal_render_returns_base64(render_secret: str) -> None:
    itinerary = {
        "city": "Jaipur",
        "total_days": 1,
        "days": [{"day_number": 1, "activities": []}],
        "poi_registry": [],
        "traveler_constraints": {"pace": "moderate"},
    }
    response = client.post(
        "/api/internal/export/render",
        json={"itinerary": itinerary, "export_format": "json"},
        headers={"X-Export-Render-Key": render_secret},
    )
    assert response.status_code == 200
    data = response.json()
    assert "content_base64" in data
    decoded = base64.b64decode(data["content_base64"])
    assert b"days" in decoded or len(decoded) > 0
