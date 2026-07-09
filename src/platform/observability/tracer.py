"""Observability — agent traces, tool calls, decisions, eval results."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class Observability:
    """In-memory span collector. Phase 0 stub; persisted/exported in later phases."""

    def __init__(self) -> None:
        self._spans: list[dict[str, Any]] = []

    def new_correlation_id(self, prefix: str = "turn") -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    def record_span(self, **fields: Any) -> dict[str, Any]:
        span = {
            "timestamp": datetime.now(UTC).isoformat(),
            **fields,
        }
        self._spans.append(span)
        return span

    def get_spans(self, correlation_id: str | None = None) -> list[dict[str, Any]]:
        if correlation_id is None:
            return list(self._spans)
        return [s for s in self._spans if s.get("correlation_id") == correlation_id]

    def get_trace(self, correlation_id: str) -> dict[str, Any]:
        return {
            "correlation_id": correlation_id,
            "spans": self.get_spans(correlation_id),
        }

    def clear(self) -> None:
        self._spans.clear()
