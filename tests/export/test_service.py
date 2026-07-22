"""Tests for Export Service rendering."""

from __future__ import annotations

SAMPLE_ITINERARY = {
    "city": "Jaipur",
    "total_days": 2,
    "traveler_constraints": {"pace": "relaxed", "interests": ["culture", "food"]},
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "id": "a1",
                    "title": "City Palace",
                    "category": "culture",
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "duration_minutes": 120,
                },
                {
                    "id": "a2",
                    "title": "Lunch at LMB",
                    "category": "food",
                    "start_time": "12:30",
                    "end_time": "13:30",
                    "duration_minutes": 60,
                },
                {
                    "id": "a3",
                    "title": "Johari Bazaar",
                    "category": "shopping",
                    "start_time": "18:00",
                    "end_time": "19:15",
                    "duration_minutes": 75,
                },
            ],
            "travel_segments": [
                {
                    "from_activity_id": "a1",
                    "to_activity_id": "a2",
                    "travel_minutes": 20,
                    "transport_mode": "drive",
                }
            ],
        }
    ],
    "poi_registry": [],
    "citations": [{"citation_id": "c1", "section": "Wikivoyage — Jaipur"}],
    "metadata": {"notes": "Pack sun protection."},
}


def test_export_markdown_includes_sections():
    from src.export.service import ExportService

    result = ExportService().export(
        itinerary=SAMPLE_ITINERARY,
        export_format="markdown",
        trip_title="Jaipur — 2-Day Trip",
    )
    text = result["content"].decode("utf-8")
    assert "# Jaipur — 2-Day Trip" in text
    assert "### Morning" in text
    assert "City Palace" in text
    assert "## Food recommendations" in text
    assert "Lunch at LMB" in text
    assert "## Shopping recommendations" in text
    assert "Johari Bazaar" in text
    assert "## Sources / References" in text
    assert "Wikivoyage" in text
    assert "Generated:" in text


def test_export_json_canonical_schema():
    import json

    from src.export.service import ExportService

    result = ExportService().export(
        itinerary=SAMPLE_ITINERARY,
        export_format="json",
    )
    payload = json.loads(result["content"].decode("utf-8"))
    assert payload["city"] == "Jaipur"
    assert payload["total_days"] == 2
    assert payload["days"][0]["day_number"] == 1
    assert payload["metadata"]["export_generated_at"]


def test_export_pdf_magic_bytes():
    from src.export.service import ExportService

    result = ExportService().export(
        itinerary=SAMPLE_ITINERARY,
        export_format="pdf",
    )
    assert result["content"][:4] == b"%PDF"
