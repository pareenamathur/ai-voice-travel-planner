"""CLI entry for n8n Execute Command — reads JSON stdin, writes export JSON stdout."""

from __future__ import annotations

import base64
import json
import sys
from typing import Any


def main() -> None:
    payload = json.load(sys.stdin)
    from src.export.service import ExportService

    result = ExportService().export(
        itinerary=payload["itinerary"],
        export_format=payload.get("export_format") or payload.get("format") or "pdf",
        trip_title=payload.get("trip_title"),
        extra_citations=payload.get("rag_citations") or [],
    )
    content: bytes = result.pop("content")
    result["content_base64"] = base64.b64encode(content).decode("ascii")
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
