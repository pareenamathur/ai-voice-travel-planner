"""Tests for export renderers."""

from __future__ import annotations

from src.export.renderers import _pdf_safe_text, render_pdf


def test_pdf_safe_text_replaces_punctuation() -> None:
    assert _pdf_safe_text("a\u2014b") == "a-b"
    assert _pdf_safe_text("a\u2013b") == "a-b"
    assert _pdf_safe_text("a\u00b7b") == "a-b"
    assert _pdf_safe_text("a\u2022b") == "a-b"


def test_pdf_safe_text_replaces_non_latin1_characters() -> None:
    result = _pdf_safe_text("जयपुर Palace")
    assert "Palace" in result
    assert "जयपुर" not in result
    result.encode("latin-1")


def test_render_pdf_accepts_unicode_activity_titles() -> None:
    context = {
        "trip_title": "Jaipur Trip",
        "city": "Jaipur",
        "total_days": 1,
        "generated_at": "2026-01-01 12:00 UTC",
        "pace": None,
        "interests": [],
        "days": [
            {
                "day_number": 1,
                "date": None,
                "notes": None,
                "blocks": {
                    "morning": [
                        {
                            "title": "जयपुर Palace",
                            "start": "09:00",
                            "end": "10:00",
                            "duration_minutes": 60,
                            "category": None,
                            "notes": None,
                        }
                    ],
                    "afternoon": [],
                    "evening": [],
                },
                "travel_notes": [],
            }
        ],
        "food_recommendations": [],
        "shopping_recommendations": [],
        "trip_notes": None,
        "sources": [],
    }
    content = render_pdf(context)
    assert content[:4] == b"%PDF"
