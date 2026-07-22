"""Tests for n8n export webhook client."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest

from src.export.service import ExportService
from src.mcp_servers.export.n8n_client import ExportWebhookError, invoke_n8n_export

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
                    "title": "Hawa Mahal",
                    "start_time": "10:00",
                    "end_time": "11:30",
                    "duration_minutes": 90,
                }
            ],
            "travel_segments": [],
        }
    ],
    "poi_registry": [],
    "citations": [],
}


@pytest.mark.asyncio
async def test_invoke_n8n_export_requires_url(monkeypatch):
    monkeypatch.setattr(
        "src.mcp_servers.export.n8n_client.settings.n8n_export_webhook_url",
        "",
    )
    with pytest.raises(ExportWebhookError, match="N8N_EXPORT_WEBHOOK_URL"):
        await invoke_n8n_export(
            itinerary=_ITINERARY,
            export_format="markdown",
        )


@pytest.mark.asyncio
async def test_invoke_n8n_export_posts_payload_and_decodes_response():
    rendered = ExportService().export(
        itinerary=_ITINERARY,
        export_format="markdown",
        trip_title="Jaipur — 1-Day Trip",
    )
    n8n_body = {
        "format": rendered["format"],
        "filename": rendered["filename"],
        "media_type": rendered["media_type"],
        "content_base64": base64.b64encode(rendered["content"]).decode("ascii"),
        "trip_title": rendered["trip_title"],
        "generated_at": rendered["generated_at"],
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: n8n_body

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.mcp_servers.export.n8n_client.settings.n8n_export_webhook_url",
            "https://n8n.example/webhook/export-itinerary",
        ),
        patch("src.mcp_servers.export.n8n_client.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await invoke_n8n_export(
            itinerary=_ITINERARY,
            export_format="markdown",
            trip_title="Jaipur — 1-Day Trip",
            rag_citations=[{"section": "Wikivoyage"}],
        )

    mock_client.post.assert_awaited_once()
    _args, kwargs = mock_client.post.await_args
    assert _args[0] == "https://n8n.example/webhook/export-itinerary"
    assert kwargs["json"]["export_format"] == "markdown"
    assert kwargs["json"]["itinerary"]["city"] == "Jaipur"
    assert b"Hawa Mahal" in result["content"]
    assert result["filename"] == rendered["filename"]


@pytest.mark.asyncio
async def test_trigger_export_gateway_delegates_to_n8n():
    from src.mcp_servers.export import trigger_export

    expected = {
        "format": "json",
        "filename": "jaipur-itinerary.json",
        "media_type": "application/json",
        "content": b"{}",
        "trip_title": "T",
        "generated_at": "2026-01-01T00:00:00+00:00",
    }

    with patch(
        "src.mcp_servers.export.invoke_n8n_export",
        new=AsyncMock(return_value=expected),
    ) as mocked:
        result = await trigger_export(
            itinerary=_ITINERARY,
            export_format="json",
            trip_title="T",
            rag_citations=[],
        )

    mocked.assert_awaited_once()
    assert result == expected
