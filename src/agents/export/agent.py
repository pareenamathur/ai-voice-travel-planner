"""Export Agent — approved itineraries only; uses Gateway ``trigger_export``."""

from __future__ import annotations

import base64
from typing import Any

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentResult, AgentRole, TaskMessage, TaskType


class ExportAgent(BaseAgent):
    """Generates downloadable exports. Returns AgentResult to Supervisor (no Review)."""

    role = AgentRole.EXPORT

    async def run(self, task: TaskMessage) -> AgentResult:
        if task.task_type != TaskType.EXPORT:
            raise ValueError(f"Export Agent requires task_type=EXPORT, got '{task.task_type}'")

        correlation_id = task.correlation_id
        self._trace("delegation_started", correlation_id, task_type=task.task_type.value)

        itinerary = task.payload.get("itinerary")
        if not isinstance(itinerary, dict):
            raise ValueError("EXPORT payload.itinerary is required")

        export_format = str(task.payload.get("format") or "pdf").lower()
        assert self.gateway is not None
        self._trace(
            "trigger_export",
            correlation_id,
            export_format=export_format,
        )
        result = await self.gateway.invoke(
            AgentRole.EXPORT,
            "trigger_export",
            {
                "itinerary": itinerary,
                "export_format": export_format,
                "trip_title": task.payload.get("trip_title"),
                "rag_citations": task.payload.get("rag_citations") or [],
            },
            correlation_id=correlation_id,
        )
        if not isinstance(result, dict) or "content" not in result:
            raise ValueError("trigger_export must return export payload with content")

        content = result["content"]
        if isinstance(content, bytes):
            encoded = base64.b64encode(content).decode("ascii")
        else:
            encoded = str(content)

        payload: dict[str, Any] = {
            "format": result.get("format", export_format),
            "filename": result.get("filename"),
            "media_type": result.get("media_type"),
            "content_base64": encoded,
            "trip_title": result.get("trip_title"),
            "generated_at": result.get("generated_at"),
        }
        self._trace(
            "export_ready",
            correlation_id,
            export_format=payload["format"],
            filename=payload.get("filename"),
        )
        return AgentResult(
            status="ok",
            payload=payload,
            correlation_id=correlation_id,
        )
