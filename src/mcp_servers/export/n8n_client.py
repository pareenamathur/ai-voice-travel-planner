"""HTTP client for the n8n export-itinerary webhook."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from src.api.config import settings


class ExportWebhookError(Exception):
    """Raised when the n8n export webhook fails or returns an invalid payload."""


async def invoke_n8n_export(
    *,
    itinerary: dict[str, Any],
    export_format: str,
    trip_title: str | None = None,
    rag_citations: list[dict[str, Any]] | None = None,
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    """POST export job to n8n; return Gateway export dict with ``content`` bytes."""
    url = (settings.n8n_export_webhook_url or "").strip()
    if not url:
        raise ExportWebhookError(
            "N8N_EXPORT_WEBHOOK_URL is not configured. "
            "Import workflows/export_itinerary.json and set the webhook URL."
        )

    payload = {
        "itinerary": itinerary,
        "export_format": export_format.lower(),
        "trip_title": trip_title,
        "rag_citations": rag_citations or [],
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ExportWebhookError(f"n8n export webhook request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:500]
        raise ExportWebhookError(
            f"n8n export webhook returned HTTP {response.status_code}: {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ExportWebhookError("n8n export webhook returned non-JSON body") from exc

    if not isinstance(data, dict):
        raise ExportWebhookError("n8n export webhook response must be a JSON object")

    encoded = data.get("content_base64")
    if not encoded or not isinstance(encoded, str):
        raise ExportWebhookError("n8n export response missing content_base64")

    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ExportWebhookError("n8n export response has invalid content_base64") from exc

    return {
        "format": data.get("format", export_format.lower()),
        "filename": data.get("filename"),
        "media_type": data.get("media_type"),
        "content": content,
        "trip_title": data.get("trip_title", trip_title),
        "generated_at": data.get("generated_at"),
    }
