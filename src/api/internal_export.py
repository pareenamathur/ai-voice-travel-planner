"""Internal export render for cloud n8n (HTTP Request node). Not part of the public UI API."""

from __future__ import annotations

import base64
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.api.config import settings
from src.export.service import ExportService

router = APIRouter(prefix="/internal/export", tags=["internal"])


class ExportRenderRequest(BaseModel):
    itinerary: dict[str, Any]
    export_format: Literal["pdf", "markdown", "json"] = Field(default="pdf", alias="format")
    trip_title: str | None = None
    rag_citations: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


@router.post("/render")
async def render_export(
    body: ExportRenderRequest,
    x_export_render_key: str | None = Header(default=None, alias="X-Export-Render-Key"),
) -> dict[str, Any]:
    """Generate export bytes for n8n when Execute Command is unavailable (n8n Cloud)."""
    secret = (settings.export_render_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=404, detail="Not found")
    if x_export_render_key != secret:
        raise HTTPException(status_code=403, detail="Invalid export render key")

    export_format = body.export_format
    result = ExportService().export(
        itinerary=body.itinerary,
        export_format=export_format,
        trip_title=body.trip_title,
        extra_citations=body.rag_citations,
    )
    content: bytes = result.pop("content")
    result["content_base64"] = base64.b64encode(content).decode("ascii")
    return result
