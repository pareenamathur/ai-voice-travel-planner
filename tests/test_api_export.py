"""API tests for itinerary export."""

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_registry, reset_registry
from src.api.main import app
from src.export.service import ExportService

client = TestClient(app)

_ITINERARY = {
    "city": "Jaipur",
    "total_days": 1,
    "traveler_constraints": {},
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "id": "a1",
                    "title": "Amber Fort",
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "duration_minutes": 120,
                }
            ],
            "travel_segments": [],
        }
    ],
    "poi_registry": [],
    "citations": [],
}


def setup_function():
    reset_registry()


@pytest.fixture(autouse=True)
def _mock_n8n_webhook(monkeypatch):
    """API export tests do not require a live n8n instance."""

    async def _fake_n8n(**kwargs):
        return ExportService().export(
            itinerary=kwargs["itinerary"],
            export_format=kwargs["export_format"],
            trip_title=kwargs.get("trip_title"),
            extra_citations=kwargs.get("rag_citations") or [],
        )

    monkeypatch.setattr(
        "src.mcp_servers.export.invoke_n8n_export",
        _fake_n8n,
    )


def test_export_rejected_when_not_approved():
    registry = get_registry()
    session = registry.session_manager.create()
    registry.session_manager.set_itinerary(
        session.session_id,
        _ITINERARY,
        poi_registry={},
        rag_citations=[],
    )
    registry.session_manager.set_itinerary_approved(session.session_id, False)

    response = client.post(
        "/api/session/export",
        json={"session_id": session.session_id, "format": "pdf"},
    )
    assert response.status_code == 400
    assert "isn't approved yet" in response.json()["detail"]


def test_export_markdown_when_approved():
    registry = get_registry()
    session = registry.session_manager.create()
    registry.session_manager.set_itinerary(
        session.session_id,
        _ITINERARY,
        poi_registry={},
        rag_citations=[],
    )
    registry.session_manager.set_itinerary_approved(session.session_id, True)

    response = client.post(
        "/api/session/export",
        json={"session_id": session.session_id, "format": "markdown"},
    )
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert b"Amber Fort" in response.content
    assert "attachment" in response.headers.get("content-disposition", "")
