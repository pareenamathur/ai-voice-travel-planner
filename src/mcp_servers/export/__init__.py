"""MCP tool handler for itinerary export (n8n webhook)."""

from __future__ import annotations

from typing import Any

from src.mcp_servers.export.n8n_client import invoke_n8n_export


async def trigger_export(
    *,
    itinerary: dict[str, Any],
    export_format: str,
    trip_title: str | None = None,
    rag_citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gateway entrypoint — delegates file generation to the n8n workflow."""
    return await invoke_n8n_export(
        itinerary=itinerary,
        export_format=export_format,
        trip_title=trip_title,
        rag_citations=rag_citations,
    )
